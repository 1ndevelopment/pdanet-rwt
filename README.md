```
            __              __      __
   ___  ___/ /__  ___  ___ / /_  __/ /_
  / _ \/ _  / _ \/ _ \/ -_) __/ /_  __/
 / .__/\_,_/\_,_/_//_/\__/\__/   /_/
/_/       Reverse WiFi Tether
```
*Portable Data Network + Reverse Wireless Tunnel*

> ***Tested on x86_64 Debian & Arch Linux with a paid version of pdanet+ running on Android 14.***

# Features

+ Tunnels traffic for various package & window managers
+ Routes packets via TCP to UDP
+ Fetches a speedier tun2socks fork ([hev-socks5-tunnel](https://github.com/heiher/hev-socks5-tunnel))
+ Improved Graphical User Interface
+ Restores to default config on exit

## Pre-Requirements

* Full version of PdaNet+
* Unlimited data plan
* Any carrier with hotspot restrictions

## How to use the script

1) Install the full version of the [PdaNet+ App](https://play.google.com/store/apps/details?id=com.pdanet) & activate with FoxFi.

2) After installing the app, launch it & tap WiFi Direct Hotspot.

3) Connect to the DIRECT-WiFi hotspot from the linux device.

4) After connecting, let's install pdanet-rwt:

```bash
git clone https://git.1ndev.com/1ndevelopment/pdanet-reverse-wireless-tunnel-dev
cd pdanet-reverse-wifi-tunnel-dev
sudo ./wizard install
```

5) Profit! Now all you have to do is launch it and follow the instructions. 

### Launch the GUI:
```bash
sudo pdanet-gui
```
### *OR* launch via into headless mode instead:
```bash
sudo pdanet-headless
```
> You now have a untethered wifi hotspot with the proper environment configurations.

** IPv4 Logs are located at ```/usr/local/bin/pdanet-rwt/logs``` after installation. 

## To-do

* Fix slow/fast realtime log output
* Focus on POSIX compliance for more portability
* Enable proxy config for WM's & Firefox based browsers
* Detect even more package managers (dnf,etc)
* Auto reconnect NIC in case of disconnect
* Choose specific tun2socks binary fork in a interactive state
* Implement non-interactive state
* Add some flags

## Legal Notice

**This script is provided for educational purposes only.**  
**This project is licensed under the [MIT License](LICENSE).**
