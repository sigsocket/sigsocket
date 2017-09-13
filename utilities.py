

from datamsg import DataMsg
from mq import MQ

import json
import logging
import random
import time


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
logger = logging.getLogger('agsigserver')


# The maximum number of preview user queue in a channel
USER_MSG_QUEUE_MAX = 200


def ok(**karg):
    """Format response arguments and return a successful result.

    Returns:
        ret (dict): The successful response.
    """
    ret = {'result': 'ok'}
    ret.update(karg)
    return ret


def failed(reason):
    """Returns a failure result.

    Args:
        reason (str): The failure reason.

    Returns:
        ret (dict): The failure response.
    """
    ret = {'result': 'failed', 'reason':reason}
    return ret


def channel_leave(user, name):
    """Called when a user wants to leave a channel.

    Args:
        user (User): a User instance that already in a channel.
        name (str): The channel name.
    """
    if name == user.channel:
        user.channel = ''

    # Clear out the user from the channel's member list.
    channel = get_channel_by_vid_name(user.vid, name)
    channel.leave(user.account, user.uid, user.line)


dict_line_to_user = {}
dict_appid_account_to_user = {}


def get_user_by_line(line):
    """Find a user with a line.

    Args:
        line (str): A string of long integer, one of unique ids of user.

    Returns:
        user (User): A User instance.
    """
    return dict_line_to_user.get(line, None)


def generate_line():
    """A line is one of the unique identifier of a user, which should be
    included when the client sends requests to the server.

    Returns:
        line (str): A string of 10-digit long integer, e.g. '9435836966'.
    """
    line = str(random.randint(9*1000*1000*1000, 10*1000*1000*1000))
    return line


# User's id, one the user's unique identifiers.
g_uid = 1000 * 1000 * 1000


def uid_create():
    """Create a uid for new user.

    Returns:
        g_uid (int): a 10-digit integer.
    """
    global g_uid
    g_uid += 1
    return g_uid


def get_user_by_appid_account(appid, account, create=False):
    """Find a user by appid and account name.

    Args:
        appid (str): ''
        account (str): The user's account name.
        create (bool): If true, create a new user if the user can't be found.

    Returns:
        user (User or None): If create true, always returns a user,
                             otherwise might be none if user does not exist.
    """
    logger.debug('Calling get_user_by_appid_account, '
                 'current dict_appid_account_to_user is {0}'
                 .format(dict_appid_account_to_user))

    k = '%s:%s' % (appid, account)
    if k not in dict_appid_account_to_user and create:
        uid = uid_create()
        user = User()
        user.uid = uid
        dict_appid_account_to_user[k] = user
    return dict_appid_account_to_user.get(k, None)


class User(object):

    def __init__(self):
        self.vid = ''
        self.account = ''
        self.uid = 0
        self.line = ''
        self.newline = ''
        self.ip = ''
        self.device = ''
        self.version = ''
        self.ver_clear =  0
        self.ver_last =  0
        self.channel = ''
        self.mq = []
        self.conn = None

    def user_login(self, account, token, device, ip, conn, ver=0):
        """
        Args:
            vid (str): client appid.
            account (str): A user's account name.
            uid (int): User id.
            token (str): Login token, could be '_no_need_token' to avoid.
            device (str): User device.
            ip (str): User ip.
            conn (SignalProtocol): User connection.
        """
        logger.info('User {0} logging in.'.format(account))

        #if vid == '': return failed('wrong vid')
        vid = ''
        if account == '': return failed('wrong account')
        if account.find(' ')>=0 : return failed('wrong account : with space')

        newline = generate_line()
        dict_line_to_user [newline] = self
        self.oldline = self.line
        self.vid  = vid
        self.account = account
        self.status = 'online'
        self.ip = ip
        self.device = device
        self.token = token
        self.version = ver

        if self.channel:
            channel_leave(self, self.channel)

        self.conn = conn
        self.line = newline

        # Init msgq
        self.sync_ver(1)

        return ok(line=newline, uid=self.uid)


    def user_getmsg(self, line, ver_clear, max, format='txt'):
        """Called when a user requests to get new messages.

        Args:
            line (str): A 10-digit integer, one of unique identifiers.
            ver_clear (int): version number of message.
            max (int): Max number of messages in a response.
            format (str): The default message format.

        Returns:
            ok (dict): The successful reulst.
        """
        logger.info('{0} is calling user_getmsg'.format(self.account))

        ver_clear = self.sync_ver(ver_clear)
        ver_next = ver_clear + 1
        msgs = []
        i = 0
        key = 'usermsg:%s' % self.uid
        while len(msgs)<max:
            _msg = self.mq_get(i)
            if _msg is None:
                ver_last = int(self.ver_last or 0)
                if len(msgs)==0 and ver_next<=ver_last:
                    ver_clear = ver_last
                break

            v , msg = _msg
            msg = DataMsg.unpack(msg)

            # cleared
            if msg is None or v <= ver_clear:
                self.mq_pop(i)
                continue

            # check lost
            if v > ver_next:
                pass

            # check expired
            if msg.is_expired():
                self.mq_pop(i)
                continue

            # add it
            msgs.append((v, msg.pack(format=format)))
            ver_next = v + 1
            i += 1
        return ok(ver_clear=ver_clear, msgs=msgs)

    def mq_pop(self, i):
        return self.mq.pop(i)

    def user_logout(self, line, ver_clear=0):

        # sync msg version
        self.sync_ver(ver_clear)

        # leave channel
        if self.channel: channel_leave(self, self.channel)

        self.conn = None
        self.line = ''
        self.status = 'offline'
        return ok()

    def user_postmsg(self, src, flag, t, content):
        """Post a message in a user's message queue.

        Args:
            src (str): The source user's account.
            flag (str): `version:level:timestamp`.
            t (str): Message type.
            content (str): Message details, usually a json object.

        Returns
            result (dict): The result indicate if successful.
        """
        msg = DataMsg(src, self.account, flag, t, time.time(), content)

        if msg.lvl in 'EL':
            #if msg.lvl == 'L' and not user.is_online():
            #    return failed('peer not online')

            # save
            v = self.add_msg(msg)

            # notify
            #if not nolog : log.info('ready notify %s %s', user.ver_clear, user.version)

            #if user.ver_clear:
            if v==self.ver_clear+1:
                self.notify('notify recvmsg %s' % json.dumps((v, msg.pack())))
            else:
                logger.info('v is {0}, self.ver_clear is {1}'.format(v, self.ver_clear))
                self.notify(['msg', v])

            return ok()

        return failed('wrong msg lvl')

    def add_msg(self, msg):
        """Add a message into user's message queue.

        Args:
            msg (str): Message details, usually a json object.

        Returns:
            ver (int): Message versionn number.
        """
        self.ver_last += 1
        ver = self.ver_last

        msgs = self.mq
        msgs.append( (ver, msg.pack()) )

        if len(msgs) > USER_MSG_QUEUE_MAX:
            msgs = msgs[-USER_MSG_QUEUE_MAX : -1]
        return ver

    def notify(self, msg):
        """Notify the user about a new message."""
        msg2 = ['notify', msg]
        self.send_to_conn(msg2)

    def user_sendmsg(self, peer, flag, t, content, line):
        """Sneds a message directly to a peer user.

        Args:
            peer (str): The user account that is supposed to receive message.
            flag (str): `version:level:timestamp`.
            t (str): Message type.
            content (str): Message details, usually a json object.
            line (str): A 10-digit integer, one of unique identifiers.

        Returns
            result (dict): The result indicate if successful.
        """
        user2 = get_user_by_appid_account( self.vid, peer)
        return user2.user_postmsg(self.account, flag, t, content)

    def voip_invite(self, func_str, channel_name, line, peer, extra):
        """Invite a user to join a channel..

        Args:
            func_str (str): The function string.
            channel_name (str): The channel name.
            line (str): A 10-digit integer, one of unique identifiers.
            peer (str): The user account that is invited.
            extra (str): Some extra message in an invitation.

        Returns
            result (dict): The result indicate if successful.
        """
        logger.debug('Calling voip_invite, func_str: {0}, channel_name: {1}, '
                     'line: {2}, peer: {3}, extra: {4}'
                     .format(func_str, channel_name, line, peer, extra))

        user2 = get_user_by_appid_account(self.vid, peer, create=True)
        flag = 'v1:E:30'
        content = json.dumps({
            'channel': channel_name,
            'extra': extra,
            'peer': self.account,
            'peeruid': self.uid,
        })

        return user2.user_postmsg(self.account, flag, func_str, content)

    def send_to_conn(self, msg):
        logger.info('Sending notify message from user {0}: {1}'
                    .format(self.account, msg))

        try:
            self.conn.sendMessage(json.dumps(msg).encode('utf8'))
        except:
            logger.error('{0} does not have a websocket connection'
                         .format(self.acount))

    def sync_ver(self, ver_clear):
        """Sync requests version number."""
        if ver_clear < self.ver_clear:
            return self.ver_clear

        if ver_clear > self.ver_clear:
            self.ver_clear = ver_clear
            if ver_clear > self.ver_last:
                self.ver_last = ver_clear
        return ver_clear

    def mq_get(self, i):
        """Get message from a user's message queue."""
        a = self.mq[i:i+1]
        return a[0] if a else None


    def channel_join(user, line, name):
        """Join a channel.

        Args:
            line (str): A 10-digit integer, one of unique identifiers.
            name (str): The channel's name.
        """
        if user.channel :
            self.channel_leave(user, name)

        user.channel = name
        channel = get_channel_by_vid_name( user.vid, name)

        return channel.join(user.account, user.uid, user.line)


cid_conns = {}


BIG_CHANNEL_NUMBER = 200


msg_max = 100 * 100


class Channel(object):
    def __init__(self, vid, name, cid):
        self.vid = vid
        self.name = name
        self.members = set()
        self.members_small = []

        self.uid_table = {}
        self.cid = cid
        self.flag = ''
        self.attrs = {}
        self.msgid = 0
        self.mq = MQ( msg_max )

    def join(self, account, uid, line):
        # check is in
        if not self.is_in(account):

            # add
            self.members_small.append( [ account, uid ] )
            if len(self.members_small) > BIG_CHANNEL_NUMBER:
                self.members_small.pop(0)

        # notify
        msgid = self.notify('channel_user_join', account, uid, line,
                            {'account':account, 'uid':uid, 'flag_channel': True,
                             'line': line, 'channel': self.name})

        self.members.add (account)

        logger.debug('Current members in channel {0} are {1}'
                     .format(self.name, account))
        logger.debug('dict_cid_to_channel is {0}'.format(dict_cid_to_channel))

        # return list, attr
        return ok(list=self.members_get(), attrs=self.get_attrs_all(),
                  cid=self.cid, msgid=msgid)

    def leave(self, account, uid, line):
        logger.info('channel leave is called by {0}'.format(account))
        # check is in
        if self.is_in(account):

            # del
            self.members.remove(account)
            self.members_small.remove( [ account, uid ] )

            # notify
            self.notify('channel_user_leave', account, uid, line,
                        {'account':account, 'uid':uid, 'channel': self.name})

        # return list, attr
        return ok(cid=self.cid)

    def send_msg(self, account, uid, line, msg, force):
        if not force and not self.is_in(account):
            logger.debug('User {0} not in channel, uid: {1}, line: {2}, '
                         'members: {3}'.format(account, uid,
                                               line, self.members))
            logger.debug('dict_cid_to_channel is {0}'.format(dict_cid_to_channel))
            return failed('not in channel')

        self.notify('channel_msg', account, uid, line,
                    {'account':account, 'uid':uid,
                     'msg':msg, 'channel':self.name})
        return ok()

    def set_attr(self, account, uid, line, k, v):
        if not self.is_in(account):
            return failed('not in channel')

        self.attrs [k] = v
        self.notify('channel_attr_update', account, uid, line,
                    {'channel':self.name, 'account':account,
                     'uid':uid, 'type':'update', 'name':k, 'value':v})
        self.notify('channel_attr_update', account, uid, line,
                    {'channel':self.name, 'account':account,
                     'uid':uid, 'type':'set', 'name':k, 'value':v})
        return ok()

    def del_attr(self, account, uid, line, k):
        if not self.is_in(account):
            return failed('not in channel')

        if k in self.attrs:
            del self.attrs[k]
        self.notify('channel_attr_update', account, uid, line,
                    {'channel':self.name, 'account':account,
                     'uid':uid, 'type':'del', 'name':k, 'value':''})
        return ok()

    def clear_attr(self, account, uid, line):
        if not self.is_in(account):
            return failed('not in channel')

        self.attrs = {}
        self.notify('channel_attr_update', account, uid, line,
                    {'channel':self.name, 'account':account, 'uid':uid,
                     'type':'clear', 'name':'', 'value':''})
        return ok()

    def get_attrs_all(self):
        return self.attrs

    def is_in(self, account):
        return account in self.members

    def members_get(self, max=BIG_CHANNEL_NUMBER):
        return self.members_small

    def query_num(self):
        return ok(num=len(self.members))

    def notify(self, t, account, uid, line, msg):
        msgid = self.msgid
        self.msgid += 1

        # msg2
        info = 'msg-v2 notify - v1:E:180 {0} {1} {2}' \
               .format(t, time.time(), json.dumps(msg))
        msg2 = ['notify', ['channel2', '', self.msgid, info]]

        for account in self.members:
            user = get_user_by_appid_account (self.vid,  account)
            user.send_to_conn(msg2)

        return msgid


dict_cid_to_channel = {}


def get_cid_by_vid_name(vid, name):
    """Get channel id by appid and channel name."""
    return '%s:%s' % (vid, name)


def get_channel_by_vid_name(vid, name, cid=None):
    """Get channel by appid and channel name, and cid if passed."""
    logger.debug('get_channel_by_vid_name is called. '
                 'vid: {0}, name: {1}, cid: {2}'.format(vid, name,cid))
    if cid is None:
        cid = get_cid_by_vid_name(vid, name)

    k = cid

    # create
    if k not in dict_cid_to_channel:
        channel = Channel(vid, name, cid)
        dict_cid_to_channel[k] = channel

    return dict_cid_to_channel[k]


def get_channel_by_cid(cid):
    return dict_cid_to_channel.get(cid, None)
