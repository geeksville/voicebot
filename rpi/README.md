fixme make this a proper guide for setting up Raspberry Pi with Tailscale and user-data modifications.

* install a virgin image on the sdcard with Raspberry Pi Imager appimage.
https://www.raspberrypi.com/software/ (this gui will guide setting wifi and network name etc...)

## temp login

ssh -o PubkeyAuthentication=no yyy@192.168.xxx

sudo raspi-config # boot/display/text console instead of gui


curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale set --ssh --operator=$USER

curl -fsSL https://ollama.com/install.sh | sh

github cli install
(type -p wget >/dev/null || (sudo apt update && sudo apt install wget -y)) \
	&& sudo mkdir -p -m 755 /etc/apt/keyrings \
	&& out=$(mktemp) && wget -nv -O$out https://cli.github.com/packages/githubcli-archive-keyring.gpg \
	&& cat $out | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
	&& sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
	&& sudo mkdir -p -m 755 /etc/apt/sources.list.d \
	&& echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
	&& sudo apt update \
	&& sudo apt install gh -y

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
* deauth github cli
* make installer script to deploy from working tree