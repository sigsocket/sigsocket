


#    _                                 _
#   /_\    __ _   ___   _ __  __ _    (_)  ___
#  //_\\  / _` | / _ \ | '__|/ _` |   | | / _ \ 
# /  _  \| (_| || (_) || |  | (_| | _ | || (_) |
# \_/ \_/ \__, | \___/ |_|   \__,_|(_)|_| \___/
#        |___/


# Calls / function strings from the client sdk.


channel_attr_calls = set([
    'channel_set_attr',
    'channel_del_attr',
    'channel_clear_attr',
])


user_calls = set([
    'user_getmsg',
    'user_logout',
    'user_sendmsg',
    'channel_join',
])


voip_calls = set([
    'voip_invite',
    'voip_invite_accept',
    'voip_invite_ack',
    'voip_invite_bye',
    'voip_invite_msg',
    'voip_invite_refuse',
])
