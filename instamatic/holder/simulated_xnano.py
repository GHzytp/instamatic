import socket
import time
from instamatic import config

localIP     = config.holder.IP_Address
localPort   = 7
bufferSize  = 255
 
remoteAddressPort   = ("127.0.0.1", 8080)

msgFromServer       = "Hello UDP Client"
bytesToSend         = str.encode(msgFromServer)

# Create a datagram socket
UDPServerSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
UDPClientSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

# Bind to address and ip
UDPServerSocket.bind((localIP, localPort))

print("UDP server up and listening")

# Listen for incoming datagrams

while(True):
    bytesAddressPair = UDPServerSocket.recvfrom(bufferSize)
    message = bytesAddressPair[0]
    address = bytesAddressPair[1]
    clientMsg = "Message from Client:{}".format(message)
    clientIP  = "Client IP Address:{}".format(address)
    print(clientMsg)
    print(clientIP)
    for i in range(257): # need to send 257 times in order to trigger the holderId update
        time.sleep(0.001) # slow down the sending process to avoid losing UDP package 
        UDPClientSocket.sendto(bytesToSend, remoteAddressPort)
        
"""
def calib_theta(theta, p):
    theta = theta + p[0] * (1 + p[1] * sin(theta + p[2]) + p[3] * sin(2 * theta + p[4]) +
    p[5] * sin(3 * theta + p[6]) + p[7] * sin(3 * theta + p[8]))
    return theta
calib_theta(-64, [0.18591734469188297973, -0.02763479830581160035, -0.47978970832006728742, -0.01033358996555580438, 0.29287147387878992300, -0.00129487322787876619, -0.06505392183984792798, -0.00229122227759024364, 0.17427033520574300440])
sin=np.sin
"""
        