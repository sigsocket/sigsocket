#    _                                 _
#   /_\    __ _   ___   _ __  __ _    (_)  ___
#  //_\\  / _` | / _ \ | '__|/ _` |   | | / _ \ 
# /  _  \| (_| || (_) || |  | (_| | _ | || (_) |
# \_/ \_/ \__, | \___/ |_|   \__,_|(_)|_| \___/
#        |___/


import time


class DataMsg(object):

    def __init__(self, src, dst, flag, t, time_start, content):
        """
        Args:
            src (str): A user that creates this message.
            dst (str): The peer should receive this message.
            flag (str): The format is like `v1:E:2592000`. `v1` is version
                        number, `E` is the level, `2592000` is the time stamp.
                        Level could be `C`(only peer connection available), `L`
                        (only peer logined) or `E`(only peer exists).
            t (str): Message type.
            time_start (time.time): Start time of this message.
            content (str): The message details.
        """
        self.src = src
        self.dst = dst
        self.flag = flag
        self.t = t
        self.content = content
        self.time_start = time_start

        if flag.startswith('v1:'):
            _, self.lvl, self.ttl = flag.split(':')
            self.ttl = int(self.ttl)

    def pack(self, format='txt'):
        if format=='json':
            return {
                'src' : self.src,
                'dst' : self.dst,
                'flag' : self.flag,
                't' : self.t,
                'content' : self.content,
                'time_start' : self.time_start,
            }
        else:
            return 'msg-v2 %s %s %s %s %d %s' % (self.src, self.dst, self.flag, self.t, self.time_start, self.content)

    def is_expired(self):
        t2 = time.time()
        t1 = self.time_start
        tt = self.ttl

        r = (t1>0) and (t2-t1>tt)
        b = t2-t1
        c = t2-t1>tt
        return r

    @staticmethod
    def unpack(line):
        try:
            time_start = 0
            if line.startswith('msg '):
                _, src, dst, flag, t, content = line.split(' ', 5)
            elif line.startswith('msg-v2 '):
                _, src, dst, flag, t, time_start, content = line.split(' ', 6)
            return DataMsg(src, dst, flag, t, int(time_start), content)
        except :
            return None
