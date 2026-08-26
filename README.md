# Domoticz---Zaptec-plugin
Domoticz plugin for managing a Zaptec charger

Introduction

With this Domoticz Plugin you can manage your Zaptec charger

Features:
- Start or Pause charging (when vehicle is connected with charger)
- Set max Amperage while charging
- Reads status
- Reads active energy consumption in Watts
- Read Total consumed energy in Kwh
- Read internal temperature of charger

Prerequests:

Python3.11 or higher (probably working with all python3 versions)

Installation:

download this git in the Domoticz plugin directory
run cd zaptec
run pip install -r requirements.txt
run sudo chown root:root *
run sudo chmod 755 plugin.py
restart domoticz with run /etc/init.d/domoticz.sh restart

Configuration:

Add Zaptec plugin on Domoticz/Settings/Hardware tab
Give it a logical name
Create an account on wwww.zaptec.com, remember the username and password
Fill the username and password of you zaptec account
Activate the plugin

Result:
- per charger, 6 devices are created:
    - Start/Pause switch
    - Amperage slider
    - Text device for status
    - Actual energy consumption
    - Total energy consumed
    - Temperature
 
Tested with Zaptec Go 2 with firmware versie 3.3.0.0, but probably works with all zaptec chargers which use the same API

Enjoy !
