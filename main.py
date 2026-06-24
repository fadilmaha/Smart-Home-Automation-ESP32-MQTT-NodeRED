# =============================
# IMPORTS
# =============================

import network
import time
import gc
from machine import Pin, ADC
from umqtt.simple import MQTTClient
import ujson


# =============================
# CONFIGURATION WIFI
# =============================

SSID = "Wokwi-GUEST"
WIFI_PASSWORD = ""

# Informations relatives au broker MQTT (cluster HiveMQ créé dans l'étape précédente)
MQTT_BROKER = "6d11058fc1944306afdf9c56d952159c.s1.eu.hivemq.cloud"
PORT = 8883

MQTT_USER = "ESP32-GSCSI-Douae"         # Nom d'utilisateur utilisé pour accès HiveMQ
MQTT_PASSWORD = "ESP32-GSCSI-Douae"     # Mot de passe utilisé pour accès HiveMQ

CLIENT_ID = "esp32_maison"


# =============================
# SÉPARATION DES MESSAGES MQTT PAR TOPICS
# =============================

TOPIC_PIR = "maison/pir"
TOPIC_LDR = "maison/ldr"
TOPIC_DIAG = "maison/diag"

TOPIC_COULOIR = "maison/couloir"
TOPIC_ECLAIRAGE = "maison/eclairage"
TOPIC_RIDEAUX = "maison/rideaux"


SEND_INTERVAL = 0.2  # Intervalle d'attente pour éviter la saturation


print("\n===== DEMARRAGE ESP32 MQTT =====")


# =============================
# INITIALISATION DES CAPTEURS ET DES ACTIONNEURS
# =============================

pir1 = Pin(6, Pin.IN)
pir2 = Pin(16, Pin.IN)

ldr1 = ADC(Pin(3))
ldr1.atten(ADC.ATTN_11DB)

ldr2 = ADC(Pin(11))
ldr2.atten(ADC.ATTN_11DB)

led_couloir = Pin(40, Pin.OUT)
led_eclairage = Pin(35, Pin.OUT)
led_rideaux = Pin(19, Pin.OUT)


# =============================
# ÉTAT ACTUEL DES ACTIONNEURS
# =============================

etat_couloir = 0
etat_eclairage = 0
etat_rideaux = 0


# =============================
# CALLBACK MQTT
# =============================

def on_message(topic, msg):

    """
    Fonction exécutée lors de la réception d'un message MQTT
    Permet de piloter LEDs et rideaux
    """

    global etat_couloir, etat_eclairage, etat_rideaux

    topic = topic.decode()                  # Décodage message MQTT reçu
    data = ujson.loads(msg)                 # Transformation du message brut reçu

    print("Message reçu:", topic, data)

    # Condition en fonction du topic du message reçu, et de la valeur du paramètre de commande

    if topic == TOPIC_COULOIR:
        etat_couloir = data.get("status", 0)
        led_couloir.value(etat_couloir)

    elif topic == TOPIC_ECLAIRAGE:
        etat_eclairage = data.get("status", 0)
        led_eclairage.value(etat_eclairage)

    elif topic == TOPIC_RIDEAUX:
        etat_rideaux = data.get("status", 0)
        led_rideaux.value(etat_rideaux)


# =============================
# CONNEXION WIFI SIMULÉE SUR WOKWI
# =============================

def connect_wifi():

    wifi = network.WLAN(network.STA_IF)
    wifi.active(True)
    wifi.connect(SSID, WIFI_PASSWORD)
    print("Connexion WiFi...")
    while not wifi.isconnected():
        time.sleep(1)
    print("WiFi connecté :", wifi.ifconfig()[0])


# =============================
# CONNEXION MQTT
# =============================

def connect_mqtt():
    global client
    # Utilisation des variables définies pour l'authentification

    client = MQTTClient(

        CLIENT_ID,
        MQTT_BROKER,
        port=PORT,
        user=MQTT_USER,
        password=MQTT_PASSWORD,
        ssl=True,
        ssl_params={"server_hostname": MQTT_BROKER}

    )
    client.set_callback(on_message)
    client.connect()
    # Abonnement aux topics des actionneurs
    client.subscribe(TOPIC_COULOIR)
    client.subscribe(TOPIC_ECLAIRAGE)
    client.subscribe(TOPIC_RIDEAUX)

    print("MQTT connecté et abonné aux commandes")


# =============================
# ENVOI DONNÉES CAPTEURS
# =============================

def publish_sensors(counter):

    # Construction du message MQTT PIR
    pir_data = {
        "id": counter,
        "pir1": pir1.value(),
        "pir2": pir2.value()

    }

    # Construction du message MQTT LDR

    ldr_data = {
        "id": counter,
        "ldr1": ldr1.read(),
        "ldr2": ldr2.read()
    }

    # Construction du message MQTT de diagnostic global

    diag_data = {
        "id": counter,
        "pir": pir_data,
        "ldr": ldr_data,
        "timestamp": time.time()
    }


    # Publication des messages MQTT vers les topics dédiés
    client.publish(TOPIC_PIR, ujson.dumps(pir_data))
    client.publish(TOPIC_LDR, ujson.dumps(ldr_data))
    client.publish(TOPIC_DIAG, ujson.dumps(diag_data))
    print("Capteurs envoyés")


# =============================
# PROGRAMME PRINCIPAL
# =============================

connect_wifi()      # Connexion Wifi
connect_mqtt()      # Connexion au broker MQTT
counter = 0         # Initialisation compteur pour identification des messages envoyés


while True:

    # Vérifie réception commandes MQTT (vidage complet de la file)
    for _ in range(10):
        client.check_msg()

    # Applique le dernier état connu aux actionneurs
    led_couloir.value(etat_couloir)
    led_eclairage.value(etat_eclairage)
    led_rideaux.value(etat_rideaux)

    # Publication des données capteurs
    publish_sensors(counter)
    counter += 1
    gc.collect()
    # Attente d'un intervalle pour éviter la saturation
    time.sleep(SEND_INTERVAL)