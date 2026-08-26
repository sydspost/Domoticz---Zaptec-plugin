#!/usr/bin/python3
#
# Domoticz Python Plugin - Zaptec Cloud API Integration met Amperage Aanpassing
#
# Author : Syds Post
# Version: 1.0.0
# Date   : 26-8-2026
#
"""
<plugin key="ZaptecCloud" name="Zaptec EV Charger via Cloud API" author="S. Post" version="1.0.0" wikilink="https://www.sydspost.nl/index.php/2026/08/26/domoticz-plugin-for-zaptec-chargers" externallink="https://www.zaptec.com/">
    <params>
        <param field="Username" label="Zaptec Gebruikersnaam / Email" width="200px" required="true" default=""/>
        <param field="Password" label="Zaptec Wachtwoord" width="200px" required="true" default="" password="true"/>
        <param field="Mode6" label="Debug" width="75px">
            <options>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal" default="true"/>
            </options>
        </param>
    </params>
</plugin>
"""
import DomoticzEx as Domoticz
from DomoticzEx import Device, Unit
import json
import urllib.request
import urllib.parse

class ZaptecPlugin:
    def __init__(self):
        self.token = ""
        self.counter = 0

    def onStart(self):
        if Parameters["Mode6"] == "Debug":
            Domoticz.Debugging(1)
        Domoticz.Log("Zaptec Cloud Plugin geïnitialiseerd.")
        self.charger_id = Parameters["Mode1"].strip()

        # Create icons if not existing
        if 'Zaptec' not in Images:
            try:
                Domoticz.Image(Filename='images.zip').Create()
            except:
                Domoticz.Log('Could not upload icons, images.zip not found in plugin file folder')

        Domoticz.Log("Create devices")
        if not self.token:
            self.get_token()
        if not self.token:
            Domoticz.Error("Geen geldige API token beschikbaar voor de opdracht.")
            return
        
        # Automatisch aanmaken van alle benodigde virtuele apparaten
        url = f"https://api.zaptec.com/api/chargers"
        req = urllib.request.Request(url, method="GET")
        req.add_header('Authorization', f'Bearer {self.token}')
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                Chargers = json.loads(response.read().decode('utf-8'))

                for charger in Chargers["Data"]:
                    deviceId = charger["DeviceId"]
                    deviceName = charger["Name"]
                    deviceFound = False

                    for Device in Devices:
                        if ((deviceId == Devices[Device].DeviceID)): 
                            deviceFound = True

                    if ((deviceFound == False)): 
                        Domoticz.Unit(Name=deviceName + ": Laadpaal Status", DeviceID=deviceId, Unit=1, TypeName="Text", Used=1, Image=Images["zaptec"].ID).Create()
                        Domoticz.Unit(Name=deviceName + ": Actueel Vermogen", DeviceID=deviceId, Unit=2, TypeName="Usage", Used=1, Image=Images["zaptec"].ID).Create()
                        Domoticz.Unit(Name=deviceName + ": Totaal Energie Verbruik", DeviceID=deviceId, Unit=3, TypeName="kWh", Used=1, Image=Images["zaptec"].ID).Create()
            
                        # Unit 4: Aan/Uit schakelaar voor Start/Stop
                        Domoticz.Unit(Name=deviceName + ": Laden Start/Pause", DeviceID=deviceId, Unit=4, TypeName="Selector Switch", Options={"LevelNames": "Start|Pause", "LevelActions": "||", "LevelOffHidden": "false", "SelectorStyle": "0"}, Used=1, Image=Images["zaptec"].ID).Create()
            
                        # Unit 5: Dimmer/Slider voor handmatige Amperage instelling (bereik 0-100% in interface)
                        Domoticz.Unit(Name=deviceName + ": Laadstroom (Amperage)", DeviceID=deviceId, Unit=5, Type=244, Subtype=73, Switchtype=7, Used=1, Image=Images["zaptec"].ID).Create()

                        # Unit 6: Temp device
                        Domoticz.Unit(Name=deviceName + ": Temperature", DeviceID=deviceId, Unit=6, Type=80, Subtype=5, Used=1, Image=Images["zaptec"].ID).Create()

        except:
            Domoticz.Log("Fout bij API aanroep")
    
        Domoticz.Log("Zaptec monitoring, bediening en amperage apparaten aangemaakt.")
        self.get_charger_status()

    def onStop(self):
        Domoticz.Log("Zaptec Cloud Plugin gestopt.")

    def onCommand(self, DeviceID, Unit, Command, Level, Color):
        Domoticz.Log(f"onCommand aangeroepen voor Device {DeviceID} Unit {Unit}: Opdracht={Command}, Level={Level}")
        
        if not self.token:
            self.get_token()
        if not self.token:
            Domoticz.Error("Geen geldige API token beschikbaar voor de opdracht.")
            return

        # retrieve Id for Device 
        url = f"https://api.zaptec.com/api/chargers"
        req = urllib.request.Request(url, method="GET")
        req.add_header('Authorization', f'Bearer {self.token}')
        req.add_header('Content-Type', 'application/json')

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                Chargers = json.loads(response.read().decode('utf-8'))

                for charger in Chargers["Data"]:
                    if charger["DeviceId"] == DeviceID:
                        id = charger["Id"]
        except:
            Domoticz.Log("onCommand: Charger not found")

        # Unit 4: Start/Pause Commando
        if Unit == 4:
            zaptec_command = "507" if Level == "0" else "506"
            if self.send_charger_command(id, zaptec_command):
                Devices[DeviceID].Units[Unit].nValue=(1 if Level == "0" else 0)
                Devices[DeviceID].Units[Unit].sValue=Level
                Devices[DeviceID].Units[Unit].Update(Log=True)

        # Unit 5: Amperage aanpassen via de Slider
        elif Unit == 5:
            # Domoticz sliders sturen waarden van 0 tot 100. We schalen dit naar 6A tot maxCurrent van je installatie.
            # Berekening: Level 0% = 6A, Level 100% = maximale laadstroom (maxCurrent). (Stapjes worden afgerond)
            maxCurrent=self.get_maxCurrent(id)
            target_amps = int(6 + (Level / 100.0) * (maxCurrent - 6))
            
            # IEC-standaard minimaliseert EV-laden tot 6A
            if target_amps < 6: target_amps = 6
            if target_amps > maxCurrent: target_amps = maxCurrent
            
            Domoticz.Log(f"Aanvraag ontvangen om lader in te stellen op {target_amps} Ampère.")
            
            if self.set_installation_amperage(installationID, target_amps):
                # Update de sliderpositie in de Domoticz interface naar de werkelijke ingestelde waarde
                Devices[DeviceID].Units[5].nValue=2
                Devices[DeviceID].Units[5].sValue=str(Level)
                Devices[DeviceID].Units[5].Update(Log=True)

    def onHeartbeat(self):
        # Beperk het aantal verzoeken om API rate limits te respecteren (elke ~50 seconden)
        self.counter += 1
        if self.counter >= 5:
            self.counter = 0
            if not self.token:
                self.get_token()
            if self.token:
                self.get_charger_status()

    def get_token(self):
        url = "https://api.zaptec.com/oauth/token"
        payload = urllib.parse.urlencode({
            'grant_type': 'password',
            'username': Parameters["Username"],
            'password': Parameters["Password"]
        }).encode('utf-8')
        
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                res = json.loads(response.read().decode('utf-8'))
                self.token = res.get("access_token", "")
                Domoticz.Debug("OAuth access token succesvol vernieuwd.")
        except Exception as e:
            Domoticz.Error(f"Verificatie bij Zaptec Cloud mislukt: {e}")

    def get_maxCurrent(self, DeviceID):
        maxCurrent = 6 # minimum of 6A conform EU regulations

        # get maxCurrent from installation
        url = f"https://api.zaptec.com/api/chargers/{DeviceID}"
        req = urllib.request.Request(url, method="GET")
        req.add_header('Authorization', f'Bearer {self.token}')
        req.add_header('Content-Type', 'application/json')

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status in [200]:
                    installationID = json.loads(response.read().decode('utf-8'))["InstallationId"]

                    url = f"https://api.zaptec.com/api/installation"
                    req = urllib.request.Request(url, method="GET")
                    req.add_header('Authorization', f'Bearer {self.token}')
        
                    with urllib.request.urlopen(req, timeout=10) as response:
                        Installations = json.loads(response.read().decode('utf-8'))

                        for installation in Installations["Data"]:
                            if ((installation["Id"] == installationID)):
                                maxCurrent = installation["MaxCurrent"]
        except Exception as e:
            Domoticz.Error(f"Fout bij ophalen maximale laadstroom op Zaptec API: {e}")

        return maxCurrent

    def get_charger_status(self):
        Domoticz.Log("Get chargers statuses")

        # retrieve Id for Device 
        url = f"https://api.zaptec.com/api/chargers"
        req = urllib.request.Request(url, method="GET")
        req.add_header('Authorization', f'Bearer {self.token}')
        req.add_header('Content-Type', 'application/json')

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                Chargers = json.loads(response.read().decode('utf-8'))

                for charger in Chargers["Data"]:
                    id = charger["Id"]
                    DeviceID = charger["DeviceId"]

                    url = f"https://api.zaptec.com/api/chargers/{id}/state"
                    req = urllib.request.Request(url, method="GET")
                    req.add_header('Authorization', f'Bearer {self.token}')
        
                    with urllib.request.urlopen(req, timeout=10) as response:
                        states = json.loads(response.read().decode('utf-8'))
                
                        temp = 0
                        power_w = 0
                        state_text = "Onbekend"
                        total_kwh = 0
                        is_charging = False
                        maxCurrent = self.get_maxCurrent(id)
                        current_max_amps = maxCurrent

                        for item in states:
                            state_id = item.get("StateId")
                            if state_id == 201:   # TemperatureInternal5
                                temp = float(item.get("ValueAsString", 0))
                            elif state_id == 513:   # Actief Vermogen (Watts)
                                power_w = float(item.get("ValueAsString", 0))
                            elif state_id == 553: # Totaal Geleverde Energie (kWh)
                                total_kwh = float(item.get("ValueAsString", 0))
                            elif state_id == 710: # Statuscode lader
                                code = item.get("ValueAsString")
                                if code == "1": 
                                    state_text = "no vehicle connected" 
                                elif code == "2":
                                    state_text = "vehicle connected, requesting to charge"
                                elif code == "3":
                                    state_text = "vehicle connected, charging"
                                    is_charging = True
                                elif code == "5":
                                    state_text = "vehicle connected, finished"
                                else:
                                    state_text = "unknown state"
                            elif state_id == 708: # Actuele ingestelde Maximaal beschikbare Amperage (L1/L2/L3 gecombineerd)
                                current_max_amps = float(item.get("ValueAsString", maxCurrent))

                # Update basis sensoren
                # Unit Laadpaal status
                Devices[DeviceID].Units[1].nValue=0
                Devices[DeviceID].Units[1].sValue=state_text
                Devices[DeviceID].Units[1].Update(Log=True)

                # Unit Actueel vermogen
                Devices[DeviceID].Units[2].nValue=0
                Devices[DeviceID].Units[2].sValue=str(int(power_w))
                Devices[DeviceID].Units[2].Update(Log=True)
                
                # Unit Totaal energie verbruik
                total_wh = total_kwh * 1000
                Devices[DeviceID].Units[3].nValue=0
                Devices[DeviceID].Units[3].sValue=f"{int(power_w)};{int(total_wh)}"
                Devices[DeviceID].Units[3].Update(Log=True)
                
                # Schakelaar synchronisatie
                if is_charging and Devices[DeviceID].Units[4].nValue == 0:
                    Devices[DeviceID].Units[4].nValue=1
                    Devices[DeviceID].Units[4].sValue="10"
                    Devices[DeviceID].Units[4].Update(Log=True)
                elif not is_charging and Devices[DeviceID].Units[4].nValue == 1:
                    Devices[DeviceID].Units[4].nValue=0
                    Devices[DeviceID].Units[4].sValue="0"
                    Devices[DeviceID].Units[4].Update(Log=True)
                
                # Schuifbalk (Slider) synchronisatie op basis van de huidige API status
                # Converteer de live ampère waarde terug naar een percentage (6A-32A -> 0-100%)
                slider_level = int(((current_max_amps - 6) / (32 - 6)) * 100)
                if slider_level < 0: slider_level = 0
                if slider_level > 100: slider_level = 100
                Devices[DeviceID].Units[5].nValue=2
                Devices[DeviceID].Units[5].sValue=str(slider_level)
                Devices[DeviceID].Units[5].Update(Log=True)
                    
                # Unit Temperature
                Devices[DeviceID].Units[6].nValue=0
                Devices[DeviceID].Units[6].sValue=f"{round(temp, 2)}"
                Devices[DeviceID].Units[6].Update(Log=True)
                
                Domoticz.Debug("Zaptec diagnostische status succesvol gesynchroniseerd.")
        except Exception as e:
            Domoticz.Error(f"Fout bij het ophalen van status van Zaptec API: {e}")
            self.token = ""

    def send_charger_command(self, id, command_id):
        url = f"https://api.zaptec.com/api/chargers/{id}/sendCommand/{command_id}"
        req = urllib.request.Request(url, method="POST")
        req.add_header('Authorization', f'Bearer {self.token}')
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status in [200, 201, 204]:
                    return True
                return False
        except Exception as e:
            Domoticz.Error(f"Fout bij verzenden van commando naar Zaptec API: {e}")
            Domoticz.Error(f"Charger is in Disconnected state; Stop/Pause command cannot be sent")
            return False

    def set_installation_amperage(self, installationID, amps):

        # Endpoint om de laadstroom dynamisch te begrenzen via de lader parameters
        url = f"https://api.zaptec.com/api/installation/{installationID}/update"
        
        # Zaptec verwacht JSON configuratie-updates
        payload = json.dumps({
            "availableCurrent": amps
        }).encode('utf-8')
        
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header('Authorization', f'Bearer {self.token}')
        req.add_header('Content-Type', 'application/json')
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status in [200]:
                    Domoticz.Log(f"Installatie succesvol begrensd op max {amps}A.")
                    return True
                else:
                    Domoticz.Error(f"Zaptec API reageerde met statuscode {response.status} bij amperage aanpassing.")
                    return False
        except Exception as e:
            Domoticz.Error(f"Fout bij aanpassen amperage op Zaptec API: {e}")
            Domoticz.Error(f"Cannot update installation when using APM")
            return True

globalPlugin = ZaptecPlugin()

def onStart(): globalPlugin.onStart()
def onStop(): globalPlugin.onStop()
def onHeartbeat(): globalPlugin.onHeartbeat()
def onCommand(DeviceID, Unit, Command, Level, Color): globalPlugin.onCommand(DeviceID, Unit, Command, Level, Color)
