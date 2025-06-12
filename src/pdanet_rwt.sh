#!/usr/bin/env bash

# Script Name: Portable Data Network + Reverse Wireless Tunnel (PDANet+ RWT)
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Jacy Kincade (1ndevelopment@protonmail.com)

# Verify root privileges & surpress Ctrl+C command output
[ "$(id -u)" -ne 0 ] && { echo "Error: Run as superuser"; exit 1 ;}
stty -echoctl

# Define the workspace
_WORKSPACE="$(dirname "$(realpath "$0")")"
# Create a directory and configure it to be the standard out for log files
mkdir -p "$_WORKSPACE/logs" ; _LOG_FILE="$_WORKSPACE/logs/pdanet_$(date +%Y%m%d_%H%M%S).log"
# The sleep 0.5 in stdout is for the script's own messages, not the tunnel binary's logs.
# It can be removed if you want the script's status messages to appear faster without any pause.
stdout() { echo -e "$@" | tee -a "$_LOG_FILE" ; sleep 0.25 ;} # Reduced sleep slightly, can be 0

# Variable configuration
_IP="192.168.49.1" _PORT="8000"
_PROXY_SERVER="http://$_IP:$_PORT"
_GITHUB_USER="heiher"
_REPO_NAME="hev-socks5-tunnel"

# Fetch latest given release from a git repo
fetch_latest_release() {
    local OS=linux
    local LATEST_RELEASE_URL=$(curl -x "$_PROXY_SERVER" -s "https://api.github.com/repos/$_GITHUB_USER/$_REPO_NAME/releases/latest" |
        grep "$_ARCH" | grep $OS | grep "browser_download_url" | sed -E 's/.*"([^"]+)".*/\1/')
    BINARY_NAME=$(echo "$LATEST_RELEASE_URL" | sed 's/.*\///')
    [ ! -f "$_WORKSPACE/$BINARY_NAME" ] && { wget -q --show-progress -e use_proxy=yes -e https_proxy="$_PROXY_SERVER" -P "$_WORKSPACE" "$LATEST_RELEASE_URL"; chmod +x "$_WORKSPACE/$BINARY_NAME"; }
    echo ""
}

# Initialize tunnel function
setup_tunnel() {
    # Configure network interface and prevent output
    { ip tuntap add mode tun dev tun0 ; ip addr add 192.168.1.1/24 dev tun0 ; ip link set dev tun0 up ;} >/dev/null 2>&1
    { ip route del default ; ip route add default via 192.168.1.1 dev tun0 metric 1 ; ip route add default via "$_IP" dev wlan0 metric 10 ;} >/dev/null 2>&1
    sysctl -w net.ipv4.conf.all.rp_filter=0 >/dev/null 2>&1
    # Configure SOCKS5 config.yml
    cat > "$_WORKSPACE/config.yml" << EOF
tunnel:
  name: tun0
  mtu: 8500
  ipv4: 192.168.1.1
socks5:
  address: $_IP
  port: $_PORT
  udp: tcp
misc:
  log-file: $_LOG_FILE
  log-level: info
EOF
    stdout "!!! Tunnel initiated on $(date) !!!\n"
    # Start SOCKS5 Binary
    "$_WORKSPACE/$BINARY_NAME" "$_WORKSPACE/config.yml" & sleep 2 # Allow binary to initialize
    # Begin logging output, using --line-buffered for grep
    tail -f "$_LOG_FILE" | \
    grep --line-buffered 'tcp' | \
    grep --line-buffered -v 'socks5 client udp construct' | \
    grep --line-buffered -v 'socks5 client res.rep 5' | \
    grep --line-buffered -v 'socks5 session handshake' | \
    awk '{print $1, $2, $7, $8, $9}'
}

# Configure system proxy
configure_proxy() {
    # Common configurations
    export http_proxy="$_PROXY_SERVER" https_proxy="$_PROXY_SERVER"
    export ftp_proxy="$_PROXY_SERVER" no_proxy="localhost,127.0.0.1"
    # Package manager specific configurations
    case "$(uname -s)" in
        Linux)
            command -v apt >/dev/null 2>&1 && echo "Acquire{HTTP::proxy \"${_PROXY_SERVER}\";HTTPS::proxy \"${_PROXY_SERVER}\";}" > /etc/apt/apt.conf.d/proxy.conf
            command -v pacman >/dev/null 2>&1 && { echo -e "use_proxy=yes\nhttp_proxy=$_PROXY_SERVER\nhttps_proxy=$_PROXY_SERVER" > /etc/wgetrc; sed -i 's/^#XferCommand = \/usr\/bin\/wget/XferCommand = \/usr\/bin\/wget/' /etc/pacman.conf; }
            command -v nix >/dev/null 2>&1 && echo -e "networking.proxy.default = \"${_PROXY_SERVER}\";\nnetworking.proxy.noProxy = \"127.0.0.1,localhost\";" | tee /etc/nix/nix.conf >/dev/null 2>&1
            ;;
        Darwin) brew config set http_proxy "$_PROXY_SERVER" && brew config set https_proxy "$_PROXY_SERVER" ;;
    esac

    # Set KDE behind proxy
    export _KDE_USER # Declare to ensure it's available if set
    _KDE_USER_CANDIDATE="$(ps aux | grep 'kwin_x11\|kwin_wayland' | grep -v grep | awk '{print $1}' | sort -u | head -n 1)"
    if [ -n "$_KDE_USER_CANDIDATE" ] && id "$_KDE_USER_CANDIDATE" &>/dev/null; then # Check if user exists
        _KDE_USER="$_KDE_USER_CANDIDATE"
        if [ -d "/home/$_KDE_USER/.config" ]; then
            [ -f "/home/$_KDE_USER/.config/kioslaverc" ] && sed -i 's/^ProxyType=.*/ProxyType=1/' "/home/$_KDE_USER/.config/kioslaverc"
            [ -f "/home/$_KDE_USER/.config/kioslaverc" ] && sed -i "s|\\(Proxy=http://\\)[^[:space:]]* [0-9]*|\\1$_IP $_PORT|g" "/home/$_KDE_USER/.config/kioslaverc"

            # Set pip behind a proxy
            mkdir -p "/home/$_KDE_USER/.config/pip" # Common user config location
            echo -e "[global]\nproxy = $_PROXY_SERVER" | tee "/home/$_KDE_USER/.config/pip/pip.conf" > /dev/null 2>&1 # Use pip.conf
        fi
    else
        echo "Warning: Could not reliably determine KDE user or user does not exist. KDE proxy settings skipped."
        _KDE_USER="" # Ensure it's empty if not found
    fi

    ## Docker Environment Proxy
    mkdir -p /etc/systemd/system/docker.service.d
    echo -e "[Service]\nEnvironment="HTTP_PROXY=http://$_IP:$_PORT"\nEnvironment="HTTPS_PROXY=$_PROXY_SERVER"\n" | tee /etc/systemd/system/docker.service.d/http-proxy.conf > /dev/null 2>&1
    systemctl restart docker >/dev/null 2>&1
    systemctl daemon-reload >/dev/null 2>&1

    # Additional tool configurations
    echo -e "proxy = $_PROXY_SERVER\n" | tee /etc/curlrc > /dev/null 2>&1
    git config --global http.proxy "$_PROXY_SERVER"
    git config --global https.proxy "$_PROXY_SERVER"
    npm config set proxy "$_PROXY_SERVER" > /dev/null 2>&1; npm config set https-proxy "$_PROXY_SERVER" > /dev/null 2>&1
}

# Final cleanup function
cleanup() {
    stdout "\n!!! Tunnel terminated on $(date) !!!\n\n"
    echo -e "Cleaning up...\n"
    # Attempt to kill the binary; redirect errors in case it's already dead
    pgrep -f "$BINARY_NAME" | xargs -r kill -9 >/dev/null 2>&1
    # Remove socks5 binary config file
    rm -f "$_WORKSPACE/config.yml"
    # Remove docker env proxy
    rm -f /etc/systemd/system/docker.service.d
    systemctl restart docker && systemctl daemon-reload
    # Unset global proxy
    unset {http,https,ftp,no}_proxy
    { git config --global --unset http.proxy ; git config --global --unset https.proxy; }
    [ -f /etc/wgetrc ] && rm /etc/wgetrc
    [ -f /etc/npmrc ] && { npm config rm proxy > /dev/null 2>&1; npm config rm https-proxy > /dev/null 2>&1; }
    [ -f /etc/curlrc ] && rm /etc/curlrc
    [ -f /etc/apt/apt.conf.d/proxy.conf ] && rm -f /etc/apt/apt.conf.d/proxy.conf
    if [ -f /etc/pacman.conf ] && grep -q "^XferCommand = /usr/bin/wget" /etc/pacman.conf; then
       sed -i 's/^XferCommand = \/usr\/bin\/wget/#XferCommand = \/usr\/bin\/wget/' /etc/pacman.conf
    fi
    if [ -f /etc/nix/nix.conf ]; then
        sed -i '/networking.proxy.default/d' /etc/nix/nix.conf
        sed -i '/networking.proxy.noProxy/d' /etc/nix/nix.conf
    fi

    # Remove proxy from KDE
    # _KDE_USER should be set if configure_proxy was successful in finding it
    if [ -n "$_KDE_USER" ] && [ -f "/home/$_KDE_USER/.config/kioslaverc" ]; then
        sed -i 's/^ProxyType=.*/ProxyType=0/' "/home/$_KDE_USER/.config/kioslaverc"
    fi

    # Remove proxy for Pip
    if [ -n "$_KDE_USER" ] && [ -f "/home/$_KDE_USER/.config/pip/pip.conf" ]; then
        rm "/home/$_KDE_USER/.config/pip/pip.conf"
    fi

    systemctl daemon-reload 2>/dev/null || true # Suppress error if not systemd
    echo "done."
    ## unsurpress ctrl+c & exit
    stty echoctl && exit 0
} ; trap cleanup SIGINT SIGTERM SIGHUP SIGQUIT #EXIT # Added to ensure cleanup on normal exit too

# Main execution
main() {
    _ARCH=$(uname -m)
    case "$_ARCH" in
        x86_64|i686|i386|arm64|aarch64)
            stdout "System Architecture: $_ARCH\n" ; fetch_latest_release
            if [ -f "$_WORKSPACE/$BINARY_NAME" ]; then
                echo "" # && read -r
                configure_proxy ; setup_tunnel
            else
                echo "Error: Failed to fetch tunnel binary!" && exit 1
            fi ;;
        *) echo -e "\nUnsupported architecture: $_ARCH\n" && exit 1 ;;
    esac
}
main
