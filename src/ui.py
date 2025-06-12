#!/usr/bin/env python3

# Script Name: Portable Data Network + Reverse Wireless Tunnel (PDANET+RWT GUI)
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Jacy Kincade (1ndevelopment@protonmail.com)

# This script provides a GUI for managing the PDANET+RWT service,
# allowing users to start and stop the tunnel, view live output,
# and monitor log files with filtered output.

import sys
import os
import subprocess
import threading
import time
import glob
import signal
import re
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                             QWidget, QPushButton, QTextEdit, QLabel, QFrame,
                             QStatusBar, QGroupBox, QGridLayout, QLineEdit, QSpinBox,
                             QMessageBox, QProgressBar, QFileDialog, QScrollBar)
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, Qt, QProcess
from PyQt5.QtGui import QFont, QTextCursor, QPalette, QColor, QIcon # <--- ADDED QIcon HERE
from PyQt5.QtWidgets import QSplitter

class ScriptRunner(QThread):
    output_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.script_path = "/usr/local/bin/pdanet-rwt-bin/pdanet_rwt.sh"
        self.process = None
        self.running = False

    def is_filtered_output(self, line):
        """Check if the line should be filtered out (suppressed)"""
        # Filter patterns - add more patterns as needed
        filter_patterns = [
            r'\[I\].*io timeout',  # Matches "[I] 0x7ff2de3faa30 io timeout"
            r'\[I\].*0x[0-9a-fA-F]+.*io timeout',  # More specific hex address + io timeout
            r'io timeout',  # Simple io timeout filter
            # Add more patterns here as needed:
            r'\[I\].*socks5 client udp construct',
            r'\[E\].*socks5 client res\.rep 5', # Note the escaped dot for "res.rep"
            r'\[E\].*socks5 session handshake',
            # r'\[D\].*debug message',  # Example: filter debug messages
            # r'warning.*connection lost',  # Example: filter connection warnings
        ]

        for pattern in filter_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                return True
        return False

    def run(self):
        try:
            self.running = True
            self.status_signal.emit("Tunnel enabled.")

            # Run the script with sudo, creating a new process group
            cmd = ['sudo', 'bash', self.script_path]
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                preexec_fn=os.setsid  # Create new process group
            )

            # Read output line by line
            while self.running and self.process.poll() is None:
                line = self.process.stdout.readline()
                if line:
                    stripped_line = line.rstrip()
                    # Only emit if not filtered
                    if not self.is_filtered_output(stripped_line):
                        self.output_signal.emit(stripped_line)

            # Get any remaining output
            if self.process.poll() is not None:
                remaining_output = self.process.stdout.read()
                if remaining_output:
                    # Split remaining output into lines and filter each
                    remaining_lines = remaining_output.rstrip().split('\n')
                    for line in remaining_lines:
                        if line and not self.is_filtered_output(line):
                            self.output_signal.emit(line)

                self.finished_signal.emit(self.process.returncode)

        except Exception as e:
            self.output_signal.emit(f"Error: {str(e)}")
            self.status_signal.emit("Error occurred")
            self.finished_signal.emit(1)

    def stop(self):
        """Send SIGINT (Ctrl+C) to the process and wait for clean shutdown"""
        self.running = False
        if self.process and self.process.poll() is None:
            try:
                self.output_signal.emit("[SYSTEM] Sending SIGINT (Ctrl+C) to tunnel process...")

                # Send SIGINT to the entire process group
                os.killpg(os.getpgid(self.process.pid), signal.SIGINT)

                # Wait for graceful shutdown (up to 10 seconds)
                self.output_signal.emit("[SYSTEM] Waiting for clean shutdown...")
                try:
                    self.process.wait(timeout=10)
                    self.output_signal.emit("[SYSTEM] Process stopped cleanly")
                except subprocess.TimeoutExpired:
                    self.output_signal.emit("[SYSTEM] Clean shutdown timeout, forcing termination...")
                    # If graceful shutdown fails, send SIGTERM
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                    try:
                        self.process.wait(timeout=3)
                        self.output_signal.emit("[SYSTEM] Process terminated")
                    except subprocess.TimeoutExpired:
                        # Last resort: SIGKILL
                        self.output_signal.emit("[SYSTEM] Force killing process...")
                        os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                        self.process.wait()
                        self.output_signal.emit("[SYSTEM] Process killed")

            except ProcessLookupError:
                # Process already terminated
                self.output_signal.emit("[SYSTEM] Process already terminated")
            except Exception as e:
                self.output_signal.emit(f"[SYSTEM] Error stopping process: {str(e)}")

class LogMonitor(QThread):
    log_signal = pyqtSignal(str)

    def __init__(self, log_file):
        super().__init__()
        self.log_file = log_file
        self.running = False

    def is_filtered_log(self, line):
        """Check if the log line should be filtered out (suppressed)"""
        # Filter patterns for log files - similar to ScriptRunner
        filter_patterns = [
            r'\[I\].*io timeout',  # Matches "[I] 0x7ff2de3faa30 io timeout"
            r'\[I\].*0x[0-9a-fA-F]+.*io timeout',  # More specific hex address + io timeout
            r'io timeout',  # Simple io timeout filter
            # Add more log-specific patterns here:
            r'\[I\].*socks5 client udp construct',
            r'\[E\].*socks5 client res\.rep 5', # Note the escaped dot for "res.rep"
            r'\[E\].*socks5 session handshake',
            # r'\[D\].*',  # Example: filter all debug messages
            # r'keepalive',  # Example: filter keepalive messages
        ]

        for pattern in filter_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                return True
        return False

    def run(self):
        self.running = True
        while self.running:
            try:
                if os.path.exists(self.log_file):
                    with open(self.log_file, 'r') as f:
                        # Go to end of file
                        f.seek(0, 2)
                        while self.running:
                            line = f.readline()
                            if line:
                                stripped_line = line.rstrip()
                                # Only emit if not filtered
                                if not self.is_filtered_log(stripped_line):
                                    self.log_signal.emit(stripped_line)
                            else:
                                time.sleep(0.1)
                else:
                    time.sleep(1)
            except Exception as e:
                self.log_signal.emit(f"Log monitor error: {str(e)}")
                time.sleep(1)

    def stop(self):
        self.running = False

class PDNRWTGui(QMainWindow):
    def __init__(self):
        super().__init__()
        self.script_runner = None
        self.log_monitor = None
        self.workspace = ""
        self.stopping = False
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Portable Data Network + Reverse Wireless Tunnel (PDANET+RWT GUI)")
        self.setGeometry(100, 100, 800, 600)

        # Set dark theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QTextEdit {
                background-color: #1e1e1e;
                color: #00ff00;
                border: 1px solid #555555;
                font-family: 'Courier New', monospace;
                font-size: 10pt;
            }
            QPushButton {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #555555;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #4c4c4c;
            }
            QPushButton:pressed {
                background-color: #2c2c2c;
            }
            QPushButton:disabled {
                background-color: #222222;
                color: #666666;
            }
            QLabel {
                color: #ffffff;
            }
            QLineEdit, QSpinBox {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #555555;
                padding: 4px;
                border-radius: 2px;
            }
            QGroupBox {
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 4px;
                margin-top: 8px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QStatusBar {
                color: #ffffff;
                background-color: #2b2b2b;
            }
        """)

        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Control buttons
        control_layout = QHBoxLayout()

        self.start_btn = QPushButton("Start Tunnel")
        self.start_btn.clicked.connect(self.start_tunnel)
        control_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop Tunnel")
        self.stop_btn.clicked.connect(self.stop_tunnel)
        self.stop_btn.setEnabled(False)
        control_layout.addWidget(self.stop_btn)

        control_layout.addStretch()
        main_layout.addLayout(control_layout)

        # Combined output and log display
        output_group = QGroupBox("Live Output (Filtered):")
        output_layout = QVBoxLayout(output_group)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont('Courier New', 10))
        output_layout.addWidget(self.output_text)

        main_layout.addWidget(output_group)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready.")

        # Display logo on startup
        self.display_logo()

    def display_logo(self):
        logo = r"""
            _                  _
  _ __   __| | __ _ _ __   ___| |_  _
 | '_ \ / _` |/ _` | '_ \ / _ \ __|| |_
 | |_) | (_| | (_| | | | |  __/ ||_   _|
 | .__/ \__,_|\__,_|_| |_|\___|\__||_|
 |_| Reverse WiFi Tether ~ GUI (v0.8)

This software is licensed under MIT License. (c) 2025
        """
        self.output_text.append(logo)

    def start_log_monitoring(self):
        """Start log monitoring after the script has had time to create log files"""
        if self.workspace:
            log_pattern = os.path.join(self.workspace, "logs", "pdanet_*.log")
            log_files = glob.glob(log_pattern)
            if log_files:
                latest_log = max(log_files, key=os.path.getctime)
                self.log_monitor = LogMonitor(latest_log)
                self.log_monitor.log_signal.connect(self.append_output)  # Use same output window
                self.log_monitor.start()
                self.append_output(f"[LOG] Started logging: {os.path.basename(latest_log)} (filtered)")
                self.append_output("─" * 60)
            else:
                # Try again in 2 seconds if no log files found yet
                self.log_timer.start(2000)

    def start_tunnel(self):
        script_path = "/usr/local/bin/pdanet-rwt-bin/pdanet_rwt.sh"

        if not os.path.exists(script_path):
            QMessageBox.critical(self, "Error", "Script file 'pdanet_rwt.sh' not found in current directory")
            return

        # Check if running as root or can sudo
        try:
            result = subprocess.run(['sudo', '-n', 'true'], capture_output=True)
            if result.returncode != 0:
                QMessageBox.critical(self, "Error",
                    "This script requires sudo privileges. Please run with sudo or configure passwordless sudo.")
                return
        except Exception as e: # Catch a broader exception for subprocess.run
            QMessageBox.critical(self, "Error", f"Unable to execute sudo command: {e}")
            return

        # Update UI state
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.stopping = False
        self.status_bar.showMessage("Tunnel enabled.")

        # Clear output
        self.output_text.clear()
        self.display_logo()

        # Start script runner
        self.script_runner = ScriptRunner()
        self.script_runner.output_signal.connect(self.append_output)
        self.script_runner.status_signal.connect(self.update_status)
        self.script_runner.finished_signal.connect(self.script_finished)
        self.script_runner.start()

        # Start log monitor with delay to allow log file creation
        self.workspace = os.path.dirname(os.path.realpath(script_path))

        # Use a timer to start log monitoring after a short delay
        self.log_timer = QTimer()
        self.log_timer.timeout.connect(self.start_log_monitoring)
        self.log_timer.setSingleShot(True)
        self.log_timer.start(2000)  # Start monitoring after 2 seconds

    def stop_tunnel(self):
        """Stop the tunnel with proper cleanup"""
        if self.stopping:
            return  # Prevent multiple stop attempts

        self.stopping = True
        self.stop_btn.setEnabled(False)
        self.status_bar.showMessage("Stopping tunnel...")

        # Stop script runner first
        if self.script_runner and self.script_runner.isRunning():
            self.script_runner.stop()
            # Wait for the script to finish stopping
            if not self.script_runner.wait(12000):  # Wait up to 12 seconds
                self.append_output("[SYSTEM] Warning: Script thread did not stop cleanly")

        # Stop log monitor
        if self.log_monitor and self.log_monitor.isRunning():
            self.log_monitor.stop()
            if not self.log_monitor.wait(3000):  # Wait up to 3 seconds
                self.append_output("[SYSTEM] Warning: Log monitor did not stop cleanly")

        # Reset UI state
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.stopping = False
        self.status_bar.showMessage("Tunnel stopped.")
        self.append_output("[SYSTEM] Tunnel stop sequence completed")

    def append_output(self, text):
        # Add timestamp and formatting for different types of output
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Detect if this is a log entry or script output
        if text.startswith("[LOG]") or text.startswith("[SYSTEM]") or "tcp" in text.lower():
            formatted_text = f"[{timestamp}] {text}"
        else:
            formatted_text = text

        # Get the vertical scroll bar
        v_scroll_bar = self.output_text.verticalScrollBar()
        # Check if the scroll bar is currently at the very bottom
        at_bottom = (v_scroll_bar.value() == v_scroll_bar.maximum())

        # Append the new text
        self.output_text.append(formatted_text)

        # Only auto-scroll to bottom if the user was already at the bottom
        if at_bottom:
            cursor = self.output_text.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.output_text.setTextCursor(cursor)

    def update_status(self, text):
        self.status_bar.showMessage(text)

    def script_finished(self, return_code):
        if not self.stopping:  # Only update UI if not manually stopping
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)

            if return_code == 0:
                self.status_bar.showMessage("Tunnel completed successfully")
            else:
                self.status_bar.showMessage(f"Tunnel exited with code: {return_code}")

    def closeEvent(self, event):
        # Clean up threads when closing
        if hasattr(self, 'log_timer'):
            self.log_timer.stop()

        if self.script_runner and self.script_runner.isRunning():
            self.script_runner.stop()
            self.script_runner.wait(5000)

        if self.log_monitor and self.log_monitor.isRunning():
            self.log_monitor.stop()
            self.log_monitor.wait(3000)

        event.accept()

def main():
    app = QApplication(sys.argv)

    # --- ICON CODE START ---
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Define the icon file name (make sure your .png file is named this)
    icon_filename = "pdanet-icon.png"
    # Construct the full path to the icon file
    icon_path = os.path.join(script_dir, icon_filename)

    # Check if the icon file exists before trying to set it
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
        print(f"Icon set from: {icon_path}") # For debugging purposes
    else:
        print(f"Warning: Icon file '{icon_filename}' not found at {icon_path}")
        # You might want to display a default icon or a message box here if it's critical
    # --- ICON CODE END ---

    # Set application properties
    app.setApplicationName("PDA_RWT GUI")
    app.setApplicationVersion("0.8")

    # Create and show main window
    window = PDNRWTGui()
    window.show()

    sys.exit(app.exec_())

if __name__ == '__main__':
    main()