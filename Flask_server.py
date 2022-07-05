from flask import Flask, render_template, url_for, request, jsonify
from ail_typo_squatting import *
import math
from uuid import uuid4

import requests

from queue import Queue
from threading import Thread

# app = Flask(__name__, static_url_path=baseUrl+'/static/')
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 900 * 1024 * 1024
app.config["DEBUG"] = False
app.config['TEMPLATES_AUTO_RELOAD'] = True

FLASK_PORT = 7005
FLASK_URL = "127.0.0.1"

num_threads = 10
sessions = list()

class Session():
    def __init__(self, url):
        self.id = str(uuid4())
        self.url = url
        self.thread_count = num_threads
        self.jobs = Queue(maxsize=0)
        self.threads = []
        self.variations_list = list()
        self.result = list()
        self.url = url

    def scan(self):
        for i in range(len(self.variations_list)):
            #need the index and the url in each queue item.
            self.jobs.put((i, self.variations_list[i]))
        for _ in range(self.thread_count):
            worker = Thread(target=self.crawl)
            worker.setDaemon(True)
            worker.start()
            self.threads.append(worker)

    def geoIp(self, ip):
        response = requests.get(f"https://ip.circl.lu/geolookup/{ip}")
        response_json = response.json()
        return response_json[0]['country_info']['Country'] 

    # Threaded function for queue processing.
    def crawl(self):
        while not self.jobs.empty():
            work = self.jobs.get()                      #fetch new work from the Queue
            try:
                data = dnsResolving([work[1]], self.url, "-")
                if 'A' in data[work[1]].keys():
                    data[work[1]]['geoip'] = self.geoIp(data[work[1]]['A'][0])
                elif 'AAAA' in data.keys():
                    data[work[1]]['geoip'] = self.geoIp(data[work[1]]['AAAA'][0])  

                # Delete empty MX records
                loc_list = list()
                for i in range(0, len(data[work[1]]['MX'])):
                    if "localhost" in data[work[1]]['MX'][i] or len(data[work[1]]['MX'][i]) < 4:
                        loc_list.append(i)
                
                for index in loc_list:
                    del data[work[1]]['MX'][index]
                
                self.result[work[0]] = data         #Store data back at correct index
            except:
                self.result[work[0]] = {}
            #signal to the queue that task has been processed
            self.jobs.task_done()
        return True

    def status(self):
        if self.jobs.empty():
            self.stop()
        total = len(self.variations_list)
        remaining = max(self.jobs.qsize(), len(self.threads))
        complete = total - remaining
        registered = sum([1 for x in self.result.copy() for e in x if len(x[e]) > 1])
        return {
            'id': self.id,
            'total': total,
            'complete': complete,
            'remaining': remaining,
            'registered': registered
            }

    def stop(self):
        self.jobs.queue.clear()
        for worker in self.threads:
            worker.join()
        self.threads.clear()

    def domains(self):
        domain = [x for x in self.result.copy() for e in x if len(x[e]) > 1]
        return domain
    
    def callVariations(self, data_dict):
        all_keys = data_dict.keys()
        if "runAll" in all_keys:
            self.variations_list = runAll(self.url, math.inf, 'txt', "-")
        else:
            if "charom" in all_keys:
                self.variations_list = characterOmission(self.url, self.variations_list, verbose=False, limit=math.inf)
            if "rep" in all_keys:
                self.variations_list = repetition(self.url, self.variations_list, verbose=False, limit=math.inf)
            if "trans" in all_keys:
                self.variations_list = transposition(self.url, self.variations_list, verbose=False, limit=math.inf)
            if "repl" in all_keys:
                self.variations_list = replacement(self.url, self.variations_list, verbose=False, limit=math.inf)
            if "dr" in all_keys:
                self.variations_list = doubleReplacement(self.url, self.variations_list, verbose=False, limit=math.inf)
            if "inser" in all_keys:
                self.variations_list = insertion(self.url, self.variations_list, verbose=False, limit=math.inf)
            if "add" in all_keys:
                self.variations_list = addition(self.url, self.variations_list, verbose=False, limit=math.inf)
            if "md" in all_keys:
                self.variations_list = missingDot(self.url, self.variations_list, verbose=False, limit=math.inf)
            if "sd" in all_keys:
                self.variations_list = stripDash(self.url, self.variations_list, verbose=False, limit=math.inf)
            if "vs" in all_keys:
                self.variations_list = vowel_swap(self.url, self.variations_list, verbose=False, limit=math.inf)
            if "hyph" in all_keys:
                self.variations_list = hyphenation(self.url, self.variations_list, verbose=False, limit=math.inf)
            if "bs" in all_keys:
                self.variations_list = bitsquatting(self.url, self.variations_list, verbose=False, limit=math.inf)
            if "homog" in all_keys:
                self.variations_list = homoglyph(self.url, self.variations_list, verbose=False, limit=math.inf)
            if "cm" in all_keys:
                self.variations_list = commonMisspelling(self.url, self.variations_list, verbose=False, limit=math.inf)
            if "homoph" in all_keys:
                self.variations_list = homophones(self.url, self.variations_list, verbose=False, limit=math.inf)
            if "wt" in all_keys:
                self.variations_list = wrongTld(self.url, self.variations_list, verbose=False, limit=math.inf)
            if "addtld" in all_keys:
                self.variations_list = addTld(self.url, self.variations_list, verbose=False, limit=math.inf)
            if "sub" in all_keys:
                self.variations_list = subdomain(self.url, self.variations_list, verbose=False, limit=math.inf)
            if "sp" in all_keys:
                self.variations_list = singularPluralize(self.url, self.variations_list, verbose=False, limit=math.inf)
            if "cdh" in all_keys:
                self.variations_list = changeDotHyph(self.url, self.variations_list, verbose=False, limit=math.inf)

        self.variations_list.insert(0, self.url)
        self.result = [{} for x in self.variations_list]
        

@app.route("/")
def index():
    return render_template("home_page.html")

@app.route("/typo", methods=['POST'])
def typo():
    data_dict = request.json["data_dict"]
    url = data_dict["url"]

    session = Session(url)
    session.callVariations(data_dict)
    session.scan()
    sessions.append(session)

    return jsonify(session.status()), 201
    
@app.route("/stop/<sid>")
def stop(sid):
    for s in sessions:
        if s.id == sid:
            s.stop()
    return jsonify({})

@app.route("/status/<sid>")
def status(sid):
    for s in sessions:
        if s.id == sid:
            return jsonify(s.status())
    return jsonify({'message': 'Scan session not found'}), 404

@app.route("/domains/<sid>")
def domains(sid):
    for s in sessions:
        if s.id == sid:
            return jsonify(s.domains())
    return jsonify({'message': 'Scan session not found'}), 404

@app.route("/download/<sid>/json")
def json(sid):
    for s in sessions:
        if s.id == sid:
            return jsonify(s.domains()), 200, {'Content-Disposition': 'attachment; filename=typo-squatting.json'}
    return jsonify({'message': 'Scan session not found'}), 404

if __name__ == "__main__":
    app.run(host=FLASK_URL, port=FLASK_PORT)