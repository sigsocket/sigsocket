Signal_ = function(serverUrl){

    function timedGetText( url, time, callback ){
        var request = new XMLHttpRequest();
        var timeout = false;
        var timer = setTimeout( function(){
            timeout = true;
            request.abort();
            callback( 'timeout', '');
        }, time );
        request.open( "GET", url );
        request.onreadystatechange = function(){
            if( request.readyState !== 4 ) return;
            if( timeout ) return;
            clearTimeout( timer );
            if( request.status === 200 ){
                callback( '', request.responseText );
            }
        }
        request.send( null );
    }

    var signal = this;

    function split_python(a,s,n){
        var x = a.split(s,n);
        var offset = 0;
        for(var i in x){
            offset += s.length + x[i].length;
        }
        x.push(a.substr(offset));
        return x;
    }

    // Session Object
    var Session = function(account, token){
        /*------------------------------------------------
        |   API : session level
        \*----------------------------------------------*/
        this.onLoginSuccess = '';
        this.onLoginFailed = '';
        this.onLogout = '';

        this.onInviteReceived = '';

        this.onMessageInstantReceive = '';

        /*------------------------------------------------
        |
        \*----------------------------------------------*/
        this.state = 'session_state_logining';
        this.line = '';
        this.uid = 0;
        this.dbg = false;
        var session = this;

        // todo lbs

        // todo set login time out

        // login
        //var socket = io('http://web.sig.agora.io/');
        var socket ;
        var dbg = function(){
            if (session.dbg){
                var x=[];for(var i in arguments)x.push(arguments[i]); console.log.apply(null, ['Agora sig dbg :'].concat(x));
            }
        };

        var do_connect = function(){
            if (1)
            {
                var url = serverUrl;
                socket = new function(){
                    var  websocket = new WebSocket(url);

                    websocket.onopen = function (evt) {
                        dbg('on conn open')
                        for(var i in bufs){
                            websocket.send( JSON.stringify( bufs[i] ) );
                        }
                    };
                    websocket.onclose = function (evt) {
                        fire('_close', '');
                        dbg('on conn close')
                    };
                    websocket.onmessage = function (evt) {
                        var msg = evt.data;
                        var x = JSON.parse(msg);
                        var name = x[0];
                        fire(x[0], x[1]);
                    };
                    websocket.onerror = function (evt) {
                        dbg('on conn error');
                        if (session.state == 'session_state_logined'){
                            fire_logout('conn error');
                        }else if (session.state == 'session_state_logining'){
                            fire_login_failed('conn err');
                        }
                    };

                    var evts = {};
                    var fire = function(evt, args){
                        if (evt in evts){
                            evts[evt]( args );
                        }
                    };
                    var bufs = [];

                    // api

                    this.on = function(evt, f){
                        evts[evt] = f;
                    }

                    this.emit = function(evt, args){
                        if (websocket.readyState == 0){
                            bufs.push( [ evt, args] );
                            return
                        }
                        websocket.send( JSON.stringify( [ evt, args] ) );
                    }

                    this.close = function(){
                        websocket.close();
                    }
                }();
            }
            session.socket = socket;

            /*------------------------------------------------
            | ping
            \*----------------------------------------------*/
            var ping_i = 0;
            var start_ping = function(){
                setTimeout(function(){
                    if (session.state != 'session_state_logined'){
                        return;
                    }
                    ping_i ++;
                    dbg('send ping' , ping_i);
                    socket.emit('ping', ping_i);
                    start_ping();
                }, 1000 * 10);
            };

            if (session.line==''){
                socket.emit('login', {
                    account:account,
                    token:token,
                    device:'websdk'
                });
                socket.on('login_ret', function(x){
                    var err = x[0];
                    var ret = JSON.parse(x[1]);
                    dbg('login ret' , err ,  ret);
                    if (!err && ret['result']=='ok'){
                        session.uid = ret['uid'];
                        session.line = ret['line'];
                        session.state = 'session_state_logined';
                        start_ping();
                        start_tick();
                        if (session.onLoginSuccess) {
                            session.onLoginSuccess(session.uid);
                        };
                        schedule_poll();
                    }else{
                        if (session.onLoginFailed){
                            session.onLoginFailed(0); // todo
                        }
                    }
                });
            }else{
                socket.emit('line_login', {line:session.line});
            }



            /*------------------------------------------------
            |   Call2
            \*----------------------------------------------*/

            var callid = 0;
            var calltable = {};
            var call_obj_table = {};

            var call2 = function(func, args, cb){
                callid ++;
                calltable[callid] = [func, args, cb];
                dbg('call ' ,[func, callid, args]);
                socket.emit('call2', [func, callid, args]);
            }

            socket.on('call2-ret', function(msg){
                var callid = msg[0];
                var err = msg[1];
                var data = msg[2];
                if (callid in calltable){
                    var cb = calltable[callid][2];
                    if (cb) cb(err, data);
                }
            });

            var is_ok = function(err, msg){
                return err=='';
            }

            var channel;

            var proc_msg1 = function(src, t, content){
                if (t=='channel_msg'){

                }
            };

            var decode_msg = function(msg){
                if (msg.startsWith("msg-v2 ")){
                    var r = split_python(msg, ' ', 6);
                    if (r.length==7){
                        var src = r[1];
                        var t = r[4];
                        var content = r[6];
                        return [src, t, content];
                    }
                }
                return null;
            }

            socket.on('pong', function(msg){
                dbg('recv pong');
            });

            socket.on('close', function(msg){
                fire_logout(0);
                socket.close();
            });

            socket.on('_close', function(msg){
                fire_logout(0);
            });

            var fire_logout = function(reason){
                if (session.state == 'session_state_logined' && session.onLogout) {
                    session.onLogout( 0 );
                }
                session.state = 'session_state_logout'
            };

            var fire_login_failed = function(reason){
                if (session.state == 'session_state_logining' && session.onLoginFailed) {
                    session.onLoginFailed( 0 );
                }
                session.state = 'session_state_logout'
            };

            /*------------------------------------------------
            |   process_msg
            \*----------------------------------------------*/

            var process_msg = function(msg){
                var tmp = msg;
                var src = tmp[0];
                var t = tmp[1];
                var content = tmp[2];

                if (t=='instant'){
                    if (session.onMessageInstantReceive) session.onMessageInstantReceive(src, 0, content);
                };

                if (t.startsWith('voip_')){
                    var root = JSON.parse(content);

                    var channel = root.channel;
                    var peer = root.peer;
                    var extra = root.extra;
                    var peeruid = root.peeruid;

                    var call;
                    if (t=='voip_invite'){
                        call = new Call(channel, peer, peeruid, extra);
                        call2('voip_invite_ack', {line:session.line, channelName:channel, peer:peer, extra:''});
                    }else{
                        call = call_obj_table[ channel + peer ];
                        if (!call){
                            return;
                        }
                    }

                    if (t=='voip_invite')     { if (session.onInviteReceived) session.onInviteReceived(call);}
                    if (t=='voip_invite_ack') { if (call.onInviteReceivedByPeer) call.onInviteReceivedByPeer(extra);}
                    if (t=='voip_invite_accept') { if (call.onInviteAcceptedByPeer) call.onInviteAcceptedByPeer(extra);}
                    if (t=='voip_invite_refuse') { if (call.onInviteRefusedByPeer) call.onInviteRefusedByPeer(extra);}
                    if (t=='voip_invite_failed') { if (call.onInviteFailed) call.onInviteFailed(extra);}
                    if (t=='voip_invite_bye') { if (call.onInviteEndByPeer) call.onInviteEndByPeer(extra);}
                    if (t=='voip_invite_msg') { if (call.onInviteMsg) call.onInviteMsg(extra);}
                }
            };


            var get_time_in_ms = function(){ return Date.now(); }

            /*------------------------------------------------
            |   poll
            \*----------------------------------------------*/
            var m_ver_clear = 0;
            var m_ver_notify = 0;
            var m_ver_ack = 0;
            var m_last_active_time = 0;
            var m_time_poll_last = 0;
            var m_is_polling = false;

            var schedule_poll = function(){
                if (m_is_polling) return;

                m_is_polling = true;

                call2('user_getmsg', {line:session.line, ver_clear:m_ver_clear, max:30}, function(err, data){
                    // todo ecode
                    if (err==''){
                        var resp = JSON.parse(data);

                        var ver_clear_old = m_ver_clear;
                        m_ver_clear = resp["ver_clear"];
                        m_ver_ack = m_ver_clear;

                        for(var i in resp["msgs"]){
                            var v = resp["msgs"][i][0];
                            var line = resp["msgs"][i][1];

                            process_msg( decode_msg( line ));

                            m_ver_clear = v;
                        }

                        if (resp["msgs"].length == 30 || m_ver_clear < m_ver_notify){
                            schedule_poll();
                        }

                        m_last_active_time = get_time_in_ms();
                    }

                    m_is_polling = false;
                    m_time_poll_last = get_time_in_ms();
                });
            };

            var schedule_poll_tail = function(){
                m_time_poll_last = get_time_in_ms();
            };

            var start_tick = function(){
                setTimeout(function(){
                    if (session.state == 'session_state_logout'){
                        return;
                    }

                    if (session.state == 'session_state_logined'){
                        var t = get_time_in_ms();

                        // poll tail
                        if (m_ver_ack < m_ver_clear && t - m_time_poll_last > 1000){
                            schedule_poll();
                        }else if (t - m_time_poll_last >= 1000 * 60 ){
                            schedule_poll();
                        }
                    }

                    start_tick();
                }, 100);
            };

            /*------------------------------------------------
            |   notify
            \*----------------------------------------------*/

            socket.on('notify', function(msg){
                dbg('recv notify ' , msg);
                if (typeof(msg)=='string'){
                    msg = split_python(msg, ' ', 2);
                    msg = msg.slice(1);
                }

                var e = msg[0];
                if (e=='channel2'){
                    var cid = msg[1];
                    var msgid = msg[2];
                    if (channel.m_channel_msgid!=0 && channel.m_channel_msgid + 1 > msgid){
                        dbg('ignore channel msg', cid, msgid, channel.m_channel_msgid)
                        return;
                    }

                    // todo : handle m_channel_msgid + 1 < msgid
                    channel.m_channel_msgid = msgid;

                    var tmp = decode_msg(msg[3]);
                    if (tmp){
                        var src = tmp[0];
                        var t = tmp[1];
                        var content = tmp[2];

                        var jj = JSON.parse(content);
                        if (t=='channel_msg'){
                            if (channel.onMessageChannelReceive){
                                channel.onMessageChannelReceive(jj.account, jj.uid, jj.msg);
                            }
                        }

                        if (t=='channel_user_join'){
                            if (channel.onChannelUserJoined){
                                channel.onChannelUserJoined(jj.account, jj.uid);
                            }
                        }

                        if (t=='channel_user_leave'){
                            if (channel.onChannelUserLeaved){
                                channel.onChannelUserLeaved(jj.account, jj.uid);
                            }
                        }

                        if (t=='channel_attr_update'){
                            if (channel.onChannelAttrUpdated){
                                channel.onChannelAttrUpdated(jj.name, jj.value, jj.type);
                            }
                        }
                    }
                }

                if (e == 'msg'){
                    m_ver_notify = msg[1];
                    schedule_poll();
                }

                if (e == 'recvmsg'){
                    var r = JSON.parse(msg[1]);
                    var v = r[0];
                    var line = r[1];
                    if (v==m_ver_clear+1){
                        process_msg( decode_msg( line ));
                        m_ver_clear = v;
                        schedule_poll_tail();
                    }else{
                        m_ver_notify = v;
                        schedule_poll();
                    }
                }
            });

            /*------------------------------------------------
            |   API : Logout
            \*----------------------------------------------*/
            session.logout = function(){
                call2('user_logout', {line:session.line}, function(err, data){
                    // todo ecode
                    fire_logout(err);
                    socket.close();
                });
            };

            /*------------------------------------------------
            |   API : Inst msg
            \*----------------------------------------------*/
            session.messageInstantSend = function(peer, msg, cb){
                call2('user_sendmsg', {line:session.line, peer:peer, flag:'v1:E:3600', t:'instant', content:msg}, function(err, data){
                    if (cb) cb( !is_ok(err, data) );
                });
            };

            /*------------------------------------------------
            |   API : Invite
            \*----------------------------------------------*/
            var Call = function(channelID, peer, extra){
                // Events
                this.onInviteReceivedByPeer = '';
                this.onInviteAcceptedByPeer = '';
                this.onInviteRefusedByPeer = '';
                this.onInviteFailed = '';
                this.onInviteEndByPeer = '';
                this.onInviteEndByMyself = '';
                this.onInviteMsg = '';
                var call = this;
                this.channelName = channelID;
                this.peer = peer;
                this.extra = extra;

                call_obj_table [ channelID + peer ] = call;

                // Actions
                this.channelInviteUser2 = function(){
                    extra = extra || '';
                    call2('voip_invite', {line:session.line, channelName:channelID, peer:peer, extra:extra} , function (err, msg){
                        if (is_ok(err, msg)){

                        }else{
                            call.onInviteFailed( err );
                        }
                    });
                };

                this.channelInviteAccept = function(extra){
                    extra = extra || '';
                    call2('voip_invite_accept', {line:session.line, channelName:channelID, peer:peer, extra:extra});
                };

                this.channelInviteRefuse = function(extra){
                    extra = extra || '';
                    call2('voip_invite_refuse', {line:session.line, channelName:channelID, peer:peer, extra:extra});
                };

                this.channelInviteDTMF = function(dtmf){
                    call2('voip_invite_msg',    {line:session.line, channelName:channelID, peer:peer, extra:JSON.stringify({msgtype:'dtmf', msgdata:dtmf})} );
                };

                this.channelInviteEnd = function(extra){
                    extra = extra || '';
                    call2('voip_invite_bye',    {line:session.line, channelName:channelID, peer:peer, extra:extra} );

                    if (call.onInviteEndByMyself) call.onInviteEndByMyself('');
                };
            };

            session.channelInviteUser2 = function(channelID, peer, extra){
                var call = new Call(channelID, peer, extra);
                call.channelInviteUser2();
                return call;
            };

            /*------------------------------------------------
            |   API : Channel
            \*----------------------------------------------*/

            session.channelJoin = function(name){
                // Channel Object
                //var channel = new function(){
                channel = new function(){
                    //
                    // Events
                    //
                    this.onChannelJoined = '';
                    this.onChannelJoinFailed = '';
                    this.onChannelLeaved = '';
                    this.onChannelUserList = '';
                    this.onChannelUserJoined = '';
                    this.onChannelUserLeaved = '';
                    this.onChannelUserList = '';
                    this.onChannelAttrUpdated = '';
                    this.onMessageChannelReceive = '';

                    this.name = name;
                    this.state = 'joining';
                    this.m_channel_msgid = 0;

                    //
                    // Actions
                    //
                    this.messageChannelSend = function(msg, f){
                        call2('channel_sendmsg', {line:session.line, name:name, msg:msg}, function(err, msg){
                            if (f){
                                f();
                            }
                        });
                    };

                    this.channelLeave = function(f){
                        call2('channel_leave', {line:session.line, name:name }, function(err, msg){
                            channel.state = 'leaved';
                            if (f){
                                f();
                            }else{
                                if (channel.onChannelLeaved){
                                    channel.onChannelLeaved(0);
                                }
                            }
                        });
                    }

                    this.channelSetAttr = function(k, v, f){
                        call2('channel_set_attr', {line:session.line, channel:name, name:k, value:v}, function(err, msg){
                            if (f){
                                f();
                            }
                        });
                    }

                    this.channelDelAttr = function(k, f){
                        call2('channel_del_attr', {line:session.line, channel:name, name:k}, function(err, msg){
                            if (f){
                                f();
                            }
                        });
                    }

                    this.channelClearAttr = function(f){
                        call2('channel_clear_attr', {line:session.line, channel:name}, function(err, msg){
                            if (f){
                                f();
                            }
                        });
                    }
                }();
                call2('channel_join', {line:session.line, name:name} , function (err, msg){
                    if (err==''){
                        channel.state = 'joined';
                        if (channel.onChannelJoined){
                            channel.onChannelJoined();
                        }
                        var r = JSON.parse(msg);
                        if (channel.onChannelUserList){
                            channel.onChannelUserList(r.list);
                        }
                        if (channel.onChannelAttrUpdated){
                            for (var k in r.attrs){
                                channel.onChannelAttrUpdated('update', k, r.attrs[k]);
                            }
                        }

                    }else{
                        if (channel.onChannelJoinFailed){
                            channel.onChannelJoinFailed(err);
                        }
                    }
                });

                return channel;
                // call2 ('....')
            }

        };

        do_connect();
    };

    this.dbg = function(a,b){
        if (a=='dbg_server'){
            this.dbg_server = b;
        }
    }

    this.login = function(account, token){
        return new Session(account, token);
    }
};

Signal = function(serverUrl){
    return new Signal_(serverUrl);
}
