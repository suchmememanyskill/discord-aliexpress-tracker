import requests, html, json

def extract_tracking_data(ids : list) -> dict:
    r = requests.get(f"https://global.cainiao.com/detail.htm?mailNoList={'%2C'.join(ids)}", headers={"Accept-Encoding": "gzip, deflate, br", "Cookie": "grayVersion=1; serverGray=1; x-hng=lang=zh-CN&language=zh-CN; arms_uid=8dc8481e-655d-4981-832d-d165752062ee; isg=BGhox0n5n43QDLP1QvZ1-p1KOlZ6kcyb8g2pfCKZj-PafQvn3aJfKcqvc42N1oRz; l=fBxEutNITcK2KFGBBOfanurza77OSIOYYuPzaNbMi95P_l1B5kCdW65r6uL6C36NFsOMR3oXCczJBeYBqQAonxvt_E6o_fkmndLHR35..; _lang=en-US; lang=en; userSelectTag=0; __wpkreporterwid_=942688db-41c4-44f6-ace1-40f5eb6b3c49"})
    c = html.unescape(r.text).split("<textarea style=\"display: none;\" id=\"waybill_list_val_box\">")[1].split("</textarea>")[0]
    return json.loads(c)

class DecodedTrackingPoint():
    def __init__(self, data : dict):
        self.desc = data["desc"]
        self.time = data["time"]
        self.timeZone = data["timeZone"]

    def __str__(self):
        return f"{self.desc} @ {self.time} {self.timeZone}"

class DecodedIndividualTrackingData:
    def __init__(self, data : dict):
        self.src = data["originCountry"]
        self.dst = data["destCountry"]
        self.cached = data["cachedTime"]
        self.id = data["mailNo"].split("(")[0]
        self.status = data["statusDesc"]
        self.points = [DecodedTrackingPoint(x) for x in data["section2"]["detailList"]]
    
    def get_last_status(self) -> str:
        if (len(self.points) > 0):
            return self.points[0].desc
        
        return self.status

    def __str__(self):
        points = ""
        if (len(self.points) > 0):
            points = "\n" + '\n'.join([str(x) for x in self.points[:5]]) + "\n"
        return f"{self.src} -> {self.dst}\n{self.status}\n{points}\nLast checked at {self.cached}"

def parse_tracking_data(data : dict) -> list:
    return [DecodedIndividualTrackingData(x) for x in data["data"]]