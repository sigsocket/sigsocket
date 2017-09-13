#    _                                 _
#   /_\    __ _   ___   _ __  __ _    (_)  ___
#  //_\\  / _` | / _ \ | '__|/ _` |   | | / _ \ 
# /  _  \| (_| || (_) || |  | (_| | _ | || (_) |
# \_/ \_/ \__, | \___/ |_|   \__,_|(_)|_| \___/
#        |___/


class MQ(object):
    def __init__(self, max = 1000 * 1000 ):
        self.v = []
        self.index = {}
        self.max = max
        self.a = 0
        self.b = 0

    def add(self, k, v):
        self.v.append((k,v))
        self.index[k] = self.b
        self.b += 1

        if len(self.v) > self.max :
            k0, _ = self.v.pop(0)
            del self.index[k0]
            self.a += 1

    def find(self, k):
        if k in self.index:
            return self.index[k] - self.a
        else:
            return None
