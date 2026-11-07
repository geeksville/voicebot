fixme make this a proper guide for setting up Raspberry Pi with Tailscale and user-data modifications.

* install a virgin image on the sdcard with Raspberry Pi Imager appimage.
https://www.raspberrypi.com/software/ (this gui will guide setting wifi and network name etc...)

## temp login

ssh -o PubkeyAuthentication=no yyy@192.168.xxx

sudo raspi-config # boot/display/text console instead of gui


curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale set --ssh --operator=$USER

curl -fsSL https://ollama.com/install.sh | sh

## todo
* make a good cloud init template per https://www.raspberrypi.com/news/cloud-init-on-raspberry-pi-os/
* install tailscale
* install ollama
* turn on fs overlay
* confirm can boot without network
* confirm all fs are read-only
* confirm connects to tailnet
* setup vscode remote development
* turn off non ts ssh
* turn on firewall to block all incoming except tailscale
* make installer script to deploy from working tree