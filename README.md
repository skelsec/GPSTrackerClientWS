# GPSTrackerClientWS
Client part of the GPSTracker suite running on websockets

The below steps are tested on Rasberry Pi 3b+

# Setup
apt install pit python3-pip
cd /home/pi/
git clone https://github.com/skelsec/aiogps.git
cd aiogps
python3 setup.py install

cd /home/pi
git clone https://github.com/skelsec/GPSTrackerClientWS.git
cd GPSTrackerClientWS
mkdir /opt/gpstracker
cp -r * /opt/gpstracker
cp example/systemd_script /etc/systemd/system/gpstracker.service

cd /opt/gpstracker
pip3 install -r requirements.txt

!!!! Get the bootstrap config from server, store it as /opt/gpstracker/bootstrap_config.json

chmod +x /opt/gpstracker/gpstracker.py
./gpstracker setup -c bootstrap_config.json

if this succseeds you'll see a config.json file created in /opt/gpstracker/

now enable and start the service
systemctl enable gpstracker
systemctal start gpstracker

to manually test the tracking process stop the service (if running)
/opt/gpstracker/gpstracker.py track