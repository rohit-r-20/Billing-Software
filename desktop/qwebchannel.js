"use strict";

var QWebChannelMessageTypes = {
    signal: 1,
    propertyUpdate: 2,
    init: 3,
    idle: 4,
    debug: 5,
    invokeMethod: 6,
    connectToSignal: 7,
    disconnectFromSignal: 8,
    setProperty: 9,
    response: 10
};

var QWebChannel = function(transport, initCallback) {
    if (typeof transport !== "object" || typeof transport.send !== "function") {
        console.error("The QWebChannel expects a transport object with a send function and onmessage callback property." +
                      " Given is: " + typeof transport);
        return;
    }

    var channel = this;
    this.transport = transport;

    this.send = function(data) {
        if (typeof(data) !== "string") {
            data = JSON.stringify(data);
        }
        channel.transport.send(data);
    };

    this.transport.onmessage = function(message) {
        var data = message.data;
        if (typeof data === "string") {
            data = JSON.parse(data);
        }
        switch (data.type) {
            case QWebChannelMessageTypes.signal:
                channel.handleSignal(data);
                break;
            case QWebChannelMessageTypes.response:
                channel.handleResponse(data);
                break;
            case QWebChannelMessageTypes.propertyUpdate:
                channel.handlePropertyUpdate(data);
                break;
            default:
                console.error("invalid message received:", message.data);
                break;
        }
    };

    this.execCallbacks = {};
    this.execId = 0;
    this.exec = function(data, callback) {
        if (!callback) {
            channel.send(data);
            return;
        }
        if (channel.execId === Number.MAX_VALUE) {
            channel.execId = Number.MIN_VALUE;
        }
        if (data.hasOwnProperty("id")) {
            console.error("Cannot exec message with pre-existing id: " + JSON.stringify(data));
            return;
        }
        var id = channel.execId++;
        channel.execCallbacks[id] = callback;
        data.id = id;
        channel.send(data);
    };

    this.objects = {};

    this.handleImage = function(response) {
        return new Promise(function(resolve, reject) {
            resolve(response);
        });
    };

    this.handleResponse = function(response) {
        if (!response.hasOwnProperty("id")) {
            console.error("Invalid response message received: ", JSON.stringify(response));
            return;
        }
        if (!channel.execCallbacks[response.id]) {
            return;
        }
        channel.execCallbacks[response.id](response.data);
        delete channel.execCallbacks[response.id];
    };

    this.handleSignal = function(message) {
        var object = channel.objects[message.object];
        if (object) {
            object.signalEmitted(message.signal, message.args);
        } else {
            console.warn("Unhandled signal: " + message.object + "::" + message.signal);
        }
    };

    this.handlePropertyUpdate = function(message) {
        for (var i in message.data) {
            var data = message.data[i];
            var object = channel.objects[data.object];
            if (object) {
                object.propertyUpdate(data.signals, data.properties);
            } else {
                console.warn("Unhandled property update: " + data.object + "::" + data.signal);
            }
        }
        channel.exec({type: QWebChannelMessageTypes.idle});
    };

    this.debug = function(message) {
        channel.send({type: QWebChannelMessageTypes.debug, data: message});
    };

    channel.exec({type: QWebChannelMessageTypes.init}, function(data) {
        for (var objectName in data) {
            var object = new QObject(objectName, data[objectName], channel);
        }
        for (var objectName in data) {
            channel.objects[objectName].initializeProperties();
        }
        if (initCallback) {
            initCallback(channel);
        }
    });
};

function QObject(name, data, webChannel) {
    this.__id__ = name;
    webChannel.objects[name] = this;

    var object = this;
    this.unwrapProperties = function() {
        for (var propertyIdx in data.properties) {
            var property = data.properties[propertyIdx];
            var propertyName = property[0];
            var propertyValue = property[1];
            object[propertyName] = propertyValue;
        }
    };

    this.unwrapMethods = function() {
        for (var methodIdx in data.methods) {
            var method = data.methods[methodIdx];
            var methodName = method[0];
            var methodId = method[1];

            object[methodName] = (function(methodId) {
                return function() {
                    var args = [];
                    var callback;
                    for (var i = 0; i < arguments.length; ++i) {
                        var arg = arguments[i];
                        if (typeof arg === "function")
                            callback = arg;
                        else
                            args.push(arg);
                    }
                    webChannel.exec({
                        type: QWebChannelMessageTypes.invokeMethod,
                        object: object.__id__,
                        method: methodId,
                        args: args
                    }, function(response) {
                        if (response !== undefined) {
                            var result = response;
                            if (callback) {
                                (callback)(result);
                            }
                        }
                    });
                };
            })(methodId);
        }
    };

    this.unwrapSignals = function() {
        for (var signalIdx in data.signals) {
            var signal = data.signals[signalIdx];
            var signalName = signal[0];
            var signalId = signal[1];
            object[signalName] = {
                connect: (function(signalName) {
                    return function(callback) {
                        if (typeof callback !== "function") {
                            console.error("Bad callback given to connect to signal " + signalName);
                            return;
                        }
                        object.__objectSignals__[signalName] = object.__objectSignals__[signalName] || [];
                        object.__objectSignals__[signalName].push(callback);
                        webChannel.exec({
                            type: QWebChannelMessageTypes.connectToSignal,
                            object: object.__id__,
                            signal: signalName
                        });
                    };
                })(signalName)
            };
        }
    };

    this.initializeProperties = function() {
        this.unwrapProperties();
        this.unwrapMethods();
        this.unwrapSignals();
    };

    this.__objectSignals__ = {};
    this.signalEmitted = function(signalName, signalArgs) {
        var callbacks = this.__objectSignals__[signalName];
        if (callbacks) {
            for (var i = 0; i < callbacks.length; ++i) {
                callbacks[i].apply(this, signalArgs);
            }
        }
    };

    this.propertyUpdate = function(signals, propertyMap) {
        for (var propertyName in propertyMap) {
            var propertyValue = propertyMap[propertyName];
            this[propertyName] = propertyValue;
        }
    };
}
