"""
Fshare Frontend - Main UI Module
PyQt5 GUI for the file sharing application
"""

import sys
import os
import logging
import time
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QPushButton, QFileDialog, 
                            QListWidget, QProgressBar, QTextEdit, QTabWidget,
                            QGroupBox, QLineEdit, QMessageBox, QComboBox, QScrollArea,
                            QAbstractItemView, QSizePolicy, QListWidgetItem)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QIcon, QFont, QPixmap

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.sender import FileSender
from backend.receiver import FileReceiver
from backend.discover import DeviceDiscovery
from backend.config import Config
from backend.utils import format_file_size, setup_logging


class TransferThread(QThread):
    """Thread for handling file transfers"""
    progress_updated = pyqtSignal(int)
    transfer_completed = pyqtSignal(bool, str)
    file_completed = pyqtSignal(str, bool, str)  
    
    def __init__(self, sender, file_paths, target_devices):
        super().__init__()
        self.sender = sender
        self.file_paths = file_paths if isinstance(file_paths, list) else [file_paths]
        self.target_devices = target_devices if isinstance(target_devices, list) else [target_devices]
        self.total_files = len(self.file_paths) * len(self.target_devices)
        self.completed_files = 0
    
    def run(self):
        try:
            total_success = True
            transfer_details = []
            
            for device in self.target_devices:
                target_ip = device['ip'] if isinstance(device, dict) else device
                device_name = device.get('name', target_ip) if isinstance(device, dict) else f"Device-{target_ip}"
                
                try:
                    
                    print(f"🚀 Starting transfer to {device_name} ({target_ip})")
                    print(f"📁 Files to transfer: {[os.path.basename(f) for f in self.file_paths]}")
                    
                    results = self.sender.send_multiple_files(
                        self.file_paths, 
                        target_ip, 
                        progress_callback=self._device_progress_callback
                    )
                    
                    print(f"📊 Transfer results for {device_name}: {results}")
                    
                    
                    device_success = True
                    for file_path, file_success in results.items():
                        file_name = os.path.basename(file_path)
                        
                       
                        if file_success:
                            print(f"✅ SUCCESS: {file_name} → {device_name}")
                            transfer_details.append(f"{file_name} to {device_name}: ✅ Success")
                        else:
                            print(f"❌ FAILED: {file_name} → {device_name}")
                            
                            
                            error_detail = "Unknown error"
                            if hasattr(self.sender, 'get_file_error'):
                                file_error = self.sender.get_file_error(file_path)
                                if file_error:
                                    error_detail = file_error
                                    print(f"   📝 Error details: {file_error}")
                            elif hasattr(self.sender, 'get_last_error'):
                                last_error = self.sender.get_last_error()
                                if last_error:
                                    error_detail = last_error
                                    print(f"   📝 Error details: {last_error}")
                            
                            transfer_details.append(f"{file_name} to {device_name}: ❌ Failed - {error_detail}")
                        
                        if file_success:
                            status_msg = f"✅ {file_name} → {device_name}"
                        else:
                            status_msg = f"❌ {file_name} → {device_name} ({error_detail})"
                        self.file_completed.emit(file_name, file_success, status_msg)
                        
                        if not file_success:
                            device_success = False
                            total_success = False
                    
                    self.completed_files += len(self.file_paths)
                    overall_progress = int((self.completed_files / self.total_files) * 100)
                    self.progress_updated.emit(overall_progress)
                    
                except Exception as e:
                    for file_path in self.file_paths:
                        file_name = os.path.basename(file_path)
                        error_msg = f"❌ {file_name} → {device_name}: Device Error - {str(e)}"
                        self.file_completed.emit(file_name, False, error_msg)
                        transfer_details.append(error_msg)
                    
                    self.completed_files += len(self.file_paths)
                    overall_progress = int((self.completed_files / self.total_files) * 100)
                    self.progress_updated.emit(overall_progress)
                    total_success = False
            
            success_count = sum(1 for detail in transfer_details if '✅ Success' in detail)
            total_count = len(transfer_details)
            
            summary = f"Transfer Summary: {success_count}/{total_count} transfers successful\n\n" + "\n".join(transfer_details)
            self.transfer_completed.emit(total_success, summary)
            
        except Exception as e:
            self.transfer_completed.emit(False, f"Transfer system error: {str(e)}")
    
    def _device_progress_callback(self, progress):
        """Handle progress for all files to one device"""
        if self.total_files > 0:
            device_index = len(self.target_devices) - len([d for d in self.target_devices if not hasattr(d, '_processed')])
            base_progress = int((self.completed_files / self.total_files) * 100)
            device_weight = len(self.file_paths) / self.total_files
            device_progress = int((progress / 100) * device_weight * 100)
            overall_progress = min(100, base_progress + device_progress)
            self.progress_updated.emit(overall_progress)


class DiscoveryThread(QThread):
    """Thread for device discovery"""
    device_found = pyqtSignal(str, str)  # IP, name
    discovery_completed = pyqtSignal()    # Discovery finished signal
    
    def __init__(self, discovery):
        super().__init__()
        self.discovery = discovery
        self.running = True
    
    def run(self):
        try:
            devices = self.discovery.discover_devices(timeout=8)
            for ip, name in devices.items():
                if self.running:  # Check if still should run
                    self.device_found.emit(ip, name)
            
            self.discovery_completed.emit()
            
        except Exception as e:
            print(f"Discovery thread error: {e}")
        finally:
            self.running = False
    
    def stop(self):
        self.running = False


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.config = Config()
        self.sender = None
        self.receiver = None
        self.discovery = None
        self.transfer_thread = None
        self.discovery_thread = None
        
        self.selected_devices = []
        
        self.real_connected_devices = {}  # Store actual connected devices with status
        
        self.connected_devices_timer = QTimer()
        self.connected_devices_timer.timeout.connect(self.update_connected_devices)
        
        self.init_ui()
        self.init_backend()
        setup_logging()
    
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Fshare - Secure File Sharing")
        
        from PyQt5.QtWidgets import QDesktopWidget
        desktop = QDesktopWidget()
        screen = desktop.screenGeometry()
        
        window_width = int(screen.width() * 0.9)  # 90% of screen width
        window_height = int(screen.height() * 0.95)  # 95% of screen height for taskbar
        
        x = (screen.width() - window_width) // 2
        y = (screen.height() - window_height) // 2
        
        self.setGeometry(x, y, window_width, window_height)
        self.setMinimumSize(1200, 900)  # Increased minimum size for better component visibility
        
        self.setWindowIcon(self.style().standardIcon(self.style().SP_ComputerIcon))
        
        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        self.create_header()
        main_layout.addWidget(self.header_widget)
        
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("mainTabWidget")
        main_layout.addWidget(self.tab_widget)
        
        self.create_send_tab()
        self.create_receive_tab()
        self.create_settings_tab()
        self.create_log_tab()
        
        self.create_status_bar()
        
        self.setup_animations()
    
    def create_header(self):
        """Create attractive header section"""
        self.header_widget = QWidget()
        self.header_widget.setObjectName("headerWidget")
        self.header_widget.setFixedHeight(80)
        
        header_layout = QHBoxLayout(self.header_widget)
        header_layout.setContentsMargins(20, 15, 20, 15)
        
        title_layout = QVBoxLayout()
        
        title_label = QLabel("Fshare")
        title_label.setObjectName("titleLabel")
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title_layout.addWidget(title_label)
        
        subtitle_label = QLabel("Secure File Sharing Made Simple")
        subtitle_label.setObjectName("subtitleLabel")
        subtitle_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title_layout.addWidget(subtitle_label)
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        
        self.connection_status = QLabel("●")
        self.connection_status.setObjectName("connectionStatus")
        self.connection_status.setAlignment(Qt.AlignCenter)
        self.connection_status.setFixedSize(20, 20)
        self.connection_status.setToolTip("Connection Status")
        header_layout.addWidget(self.connection_status)
        
        self.update_connection_status(False)
    
    def create_send_tab(self):
        """Create the send files tab"""
        send_widget = QWidget()
        layout = QVBoxLayout(send_widget)
        
        file_group = QGroupBox("📁 Select Files")
        file_group.setObjectName("fileSelectionGroup")
        file_layout = QVBoxLayout(file_group)
        file_layout.setSpacing(10)
        
        self.file_list = QListWidget()
        self.file_list.setObjectName("fileListWidget")
        self.file_list.setMinimumHeight(150)  # Set minimum height for better visibility
        
        from PyQt5.QtWidgets import QAbstractItemView
        self.file_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.file_list.setSelectionBehavior(QAbstractItemView.SelectRows)
        
        self.file_list.setStyleSheet("""
            QListWidget {
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                padding: 5px;
                color: white;
            }
            QListWidget::item {
                padding: 8px;
                margin: 2px;
                border-radius: 4px;
                background-color: rgba(255, 255, 255, 0.05);
            }
            QListWidget::item:selected {
                background-color: rgba(42, 130, 218, 0.8);
                color: white;
                font-weight: bold;
            }
            QListWidget::item:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
        """)
        
        file_layout.addWidget(self.file_list)
        
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        self.add_file_btn = QPushButton("📎 Add Files")
        self.add_file_btn.setObjectName("addFileButton")
        self.add_file_btn.clicked.connect(self.add_files)
        self.add_file_btn.setMinimumHeight(35)
        
        self.remove_file_btn = QPushButton("🗑️ Remove Selected")
        self.remove_file_btn.setObjectName("removeFileButton")
        self.remove_file_btn.clicked.connect(self.remove_files)
        self.remove_file_btn.setMinimumHeight(35)
        
        button_layout.addWidget(self.add_file_btn)
        button_layout.addWidget(self.remove_file_btn)
        file_layout.addLayout(button_layout)
        
        layout.addWidget(file_group)
        
        connected_group = QGroupBox("🟢 Connected Devices")
        connected_group.setObjectName("connectedDevicesGroup")
        connected_layout = QVBoxLayout(connected_group)
        connected_layout.setSpacing(8)
        connected_layout.setContentsMargins(15, 10, 15, 10)
        
        connected_group.setStyleSheet("""
            QGroupBox#connectedDevicesGroup {
                font-weight: bold;
                font-size: 13px;
                color: #28a745;
                border: 2px solid rgba(40, 167, 69, 0.3);
                border-radius: 10px;
                margin: 5px;
                padding-top: 10px;
                background-color: rgba(40, 167, 69, 0.1);
            }
            QGroupBox#connectedDevicesGroup::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                background-color: rgba(40, 167, 69, 0.2);
                border-radius: 4px;
                color: #28a745;
            }
        """)
        
        self.connected_devices_list = QListWidget()
        self.connected_devices_list.setObjectName("connectedDevicesWidget")
        self.connected_devices_list.setMinimumHeight(80)  # Increased from 60
        self.connected_devices_list.setMaximumHeight(150)  # Increased from 100 for better visibility
        self.connected_devices_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.connected_devices_list.customContextMenuRequested.connect(self.show_connected_device_context_menu)
        self.connected_devices_list.setStyleSheet("""
            QListWidget#connectedDevicesWidget {
                background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(79, 172, 254, 0.3);
                border-radius: 10px;
                color: #ffffff;
                font-size: 12px;
                padding: 8px;
            }
            QListWidget#connectedDevicesWidget::item {
                padding: 12px 15px;
                border-radius: 6px;
                margin: 3px 2px;
                background-color: rgba(79, 172, 254, 0.15);
                border-left: 3px solid #4facfe;
                color: #ffffff;
                font-weight: bold;
            }
            QListWidget#connectedDevicesWidget::item:hover {
                background-color: rgba(79, 172, 254, 0.25);
                border-left: 3px solid #00f2fe;
                transform: scale(1.02);
            }
            QListWidget#connectedDevicesWidget::item:selected {
                background-color: rgba(79, 172, 254, 0.35);
                border-left: 3px solid #00f2fe;
            }
        """)
        
        placeholder_connected = QListWidgetItem("⏳ No devices connected yet - Start transfers to see active connections")
        placeholder_connected.setFlags(placeholder_connected.flags() & ~Qt.ItemIsSelectable)
        self.connected_devices_list.addItem(placeholder_connected)
        
        connected_layout.addWidget(self.connected_devices_list)
        
        status_layout = QHBoxLayout()
        status_icon = QLabel("🔄")
        status_icon.setStyleSheet("font-size: 16px;")
        status_text = QLabel("Real-time connection monitoring active")
        status_text.setStyleSheet("""
            color: #28a745; 
            font-size: 11px; 
            font-style: italic;
            padding: 5px;
        """)
        status_layout.addWidget(status_icon)
        status_layout.addWidget(status_text)
        status_layout.addStretch()
        connected_layout.addLayout(status_layout)
        
        layout.addWidget(connected_group)
        
        device_group = QGroupBox("Connect to Device")
        device_layout = QVBoxLayout(device_group)
        
        connection_tabs = QTabWidget()
        
        discovery_tab = QWidget()
        discovery_layout = QVBoxLayout(discovery_tab)
        discovery_layout.setSpacing(10)
        discovery_layout.setContentsMargins(10, 10, 10, 10)
        
        discovery_scroll_area = QScrollArea()
        discovery_scroll_area.setWidgetResizable(True)
        discovery_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        discovery_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)  # Show scrollbar when needed
        discovery_scroll_area.setFrameShape(QScrollArea.NoFrame)
        discovery_scroll_area.setSizeAdjustPolicy(QScrollArea.AdjustToContents)
        
        self.discovery_scroll_area = discovery_scroll_area
        
        discovery_scrollbar = discovery_scroll_area.verticalScrollBar()
        discovery_scrollbar.setSingleStep(8)   # Smaller steps for ultra-smooth scrolling
        discovery_scrollbar.setPageStep(40)    # Reduced page step for fine control
        
        discovery_scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: rgba(255, 255, 255, 0.15);
                width: 16px;
                border-radius: 8px;
                margin: 0px;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            QScrollBar::handle:vertical {
                background-color: rgba(79, 172, 254, 0.8);
                border-radius: 7px;
                min-height: 30px;
                margin: 1px;
                border: 1px solid rgba(79, 172, 254, 0.4);
            }
            QScrollBar::handle:vertical:hover {
                background-color: #4facfe;
                border: 1px solid rgba(79, 172, 254, 0.6);
            }
            QScrollBar::handle:vertical:pressed {
                background-color: #3f9cfe;
                border: 1px solid #4facfe;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 16px;
                width: 16px;
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                margin: 0px;
            }
            QScrollBar::add-line:vertical:hover,
            QScrollBar::sub-line:vertical:hover {
                background-color: rgba(79, 172, 254, 0.3);
            }
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: rgba(255, 255, 255, 0.05);
                border-radius: 4px;
            }
        """)
        
        discovery_scroll_content = QWidget()
        discovery_scroll_content_layout = QVBoxLayout(discovery_scroll_content)
        discovery_scroll_content_layout.setSpacing(15)  # Reduced spacing to fit more content
        discovery_scroll_content_layout.setContentsMargins(15, 15, 15, 15)  # Reduced margins
        
        discovery_scroll_content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        discovery_section = QGroupBox()
        discovery_section.setObjectName("deviceDiscoverySection")
        discovery_section_layout = QVBoxLayout(discovery_section)
        discovery_section_layout.setSpacing(15)  # Reduced spacing between elements
        discovery_section_layout.setContentsMargins(20, 20, 20, 20)  # Balanced padding
        
        discovery_section.setMinimumHeight(0)  # Remove minimum height restriction
        discovery_section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # Allow full expansion
        
        discovery_section.setStyleSheet("""
            QGroupBox {
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
                margin-top: 10px;
                padding-top: 15px;
            }
        """)
        
        device_label = QLabel("🔍 Available Devices (Hold Ctrl for multiple):")
        device_label.setObjectName("deviceLabel")
        device_label.setMinimumHeight(45)  # Ensure sufficient height
        device_label.setStyleSheet("""
            QLabel {
                font-weight: bold; 
                font-size: 14px; 
                color: #ffffff;
                margin-bottom: 10px;
                padding: 12px 15px;
                background-color: rgba(79, 172, 254, 0.25);
                border-radius: 8px;
                border-left: 4px solid #4facfe;
                min-height: 35px;
            }
        """)
        discovery_section_layout.addWidget(device_label)
        
        self.device_list = QListWidget()
        self.device_list.setObjectName("deviceListWidget")
        self.device_list.setMinimumHeight(160)  # Minimum height for visibility
        self.device_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.device_list.setSelectionMode(QAbstractItemView.ExtendedSelection)  # Allow multiple selection
        
        self.device_list.setStyleSheet("""
            QListWidget {
                background-color: rgba(255, 255, 255, 0.1);
                border: 2px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                color: white;
                font-size: 12px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 12px 15px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                margin: 2px;
                background-color: rgba(255, 255, 255, 0.05);
            }
            QListWidget::item:selected {
                background-color: rgba(42, 130, 218, 0.8);
                color: white;
                font-weight: bold;
            }
            QListWidget::item:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
        """)
        
        placeholder_item = QListWidgetItem("No devices found - Click refresh to scan")
        placeholder_item.setFlags(placeholder_item.flags() & ~Qt.ItemIsSelectable)  # Make it non-selectable
        self.device_list.addItem(placeholder_item)
        
        discovery_section_layout.addWidget(self.device_list)
        
        discovery_section_layout.addSpacing(10)  # Reduced spacing
        
        device_buttons_layout = QHBoxLayout()
        device_buttons_layout.setSpacing(10)  # Reduced spacing between buttons
        
        self.refresh_btn = QPushButton("🔄 Refresh Devices")
        self.refresh_btn.setObjectName("refreshButton")
        self.refresh_btn.clicked.connect(self.refresh_devices)
        self.refresh_btn.setMinimumHeight(42)  # Reduced from 50 to 42 for compact layout
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #28a745, stop:1 #20c997);
                border: none;
                border-radius: 22px;
                color: white;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #34ce57, stop:1 #2dd4aa);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1e7e34, stop:1 #1aa179);
            }
            QPushButton:disabled {
                background: #666666;
                color: #999999;
            }
        """)
        device_buttons_layout.addWidget(self.refresh_btn)
        
        self.manual_ip_btn = QPushButton("📍 Manual IP")
        self.manual_ip_btn.setObjectName("manualIPButton")
        self.manual_ip_btn.clicked.connect(self.add_manual_device)
        self.manual_ip_btn.setMinimumHeight(42)  # Reduced from 50 to 42 for compact layout
        self.manual_ip_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffc107, stop:1 #fd7e14);
                border: none;
                border-radius: 22px;
                color: white;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffcd39, stop:1 #ff8c42);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #e0a800, stop:1 #dc5912);
            }
            QPushButton:disabled {
                background: #666666;
                color: #999999;
            }
        """)
        device_buttons_layout.addWidget(self.manual_ip_btn)
        
        self.help_btn = QPushButton("❓ Help")
        self.help_btn.setObjectName("helpButton")
        self.help_btn.clicked.connect(self.show_device_help)
        self.help_btn.setMinimumHeight(42)  # Match other buttons
        self.help_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #6f42c1, stop:1 #495057);
                border: none;
                border-radius: 22px;
                color: white;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #7952cc, stop:1 #5a6268);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5d3ba7, stop:1 #495057);
            }
            QPushButton:disabled {
                background: #666666;
                color: #999999;
            }
        """)
        device_buttons_layout.addWidget(self.help_btn)
        
        discovery_section_layout.addLayout(device_buttons_layout)
        
        discovery_section_layout.addSpacing(10)  # Reduced spacing
        
        self.discovery_status = QLabel("Ready to scan for devices")
        self.discovery_status.setObjectName("discoveryStatus")
        self.discovery_status.setAlignment(Qt.AlignCenter)
        self.discovery_status.setStyleSheet("""
            QLabel {
                color: #888888; 
                font-style: italic; 
                font-size: 11px;
                padding: 8px 12px;
                background-color: rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                margin: 5px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        self.discovery_status.setMinimumHeight(35)  # Reduced height
        discovery_section_layout.addWidget(self.discovery_status)
        
        discovery_section_layout.addSpacing(10)  # Minimal bottom padding
        
        discovery_scroll_content_layout.addWidget(discovery_section)
        
        discovery_scroll_content_layout.addStretch()
        discovery_scroll_content_layout.addSpacing(20)  # Reduced bottom padding
        
        discovery_scroll_area.setWidget(discovery_scroll_content)
        
        self.setup_enhanced_smooth_scrolling(discovery_scroll_area)
        
        discovery_layout.addWidget(discovery_scroll_area)
        
        connection_tabs.addTab(discovery_tab, "Auto Discovery")
        
        QTimer.singleShot(500, self.ensure_discovery_scroll_works)
        
        link_tab = QWidget()
        link_layout = QVBoxLayout(link_tab)
        link_layout.setSpacing(10)
        link_layout.setContentsMargins(10, 10, 10, 10)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        
        scroll_content = QWidget()
        scroll_content_layout = QVBoxLayout(scroll_content)
        scroll_content_layout.setSpacing(15)
        scroll_content_layout.setContentsMargins(15, 15, 15, 15)
        
        link_section = QWidget()
        link_section.setObjectName("connectionLinkSection")
        link_section_layout = QVBoxLayout(link_section)
        link_section_layout.setSpacing(10)
        link_section_layout.setContentsMargins(15, 15, 15, 15)
        
        link_section.setStyleSheet("""
            QWidget#connectionLinkSection {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                margin: 5px;
            }
        """)
        
        link_label = QLabel("📋 Paste Connection Link:")
        link_label.setObjectName("connectionLabel")
        link_label.setStyleSheet("font-weight: bold; color: #ffffff; font-size: 12px;")
        link_section_layout.addWidget(link_label)
        
        self.connection_link_input = QLineEdit()
        self.connection_link_input.setObjectName("connectionLinkInput")
        self.connection_link_input.setPlaceholderText("fshare://connect/...")
        self.connection_link_input.setMinimumHeight(40)
        self.connection_link_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.1);
                border: 2px solid rgba(255, 255, 255, 0.2);
                border-radius: 20px;
                padding: 8px 15px;
                color: white;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 2px solid #4facfe;
                background-color: rgba(255, 255, 255, 0.15);
            }
            QLineEdit::placeholder {
                color: rgba(255, 255, 255, 0.6);
            }
        """)
        link_section_layout.addWidget(self.connection_link_input)
        
        self.connect_link_btn = QPushButton("🔗 Connect via Link")
        self.connect_link_btn.setObjectName("connectLinkButton")
        self.connect_link_btn.clicked.connect(self.connect_via_link)
        self.connect_link_btn.setMinimumHeight(45)
        self.connect_link_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4facfe, stop:1 #00f2fe);
                border: none;
                border-radius: 22px;
                color: white;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5fbdff, stop:1 #1ff3ff);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3f9cfe, stop:1 #00e2ee);
            }
            QPushButton:disabled {
                background: #666666;
                color: #999999;
            }
        """)
        link_section_layout.addWidget(self.connect_link_btn)
        
        scroll_content_layout.addWidget(link_section)
        
        separator_widget = QWidget()
        separator_widget.setFixedHeight(30)
        separator_layout = QHBoxLayout(separator_widget)
        separator_layout.setContentsMargins(20, 10, 20, 10)
        
        separator_line1 = QWidget()
        separator_line1.setFixedHeight(1)
        separator_line1.setStyleSheet("background: linear-gradient(to right, transparent, #666666, transparent);")
        separator_layout.addWidget(separator_line1, 2)
        
        or_label = QLabel("OR")
        or_label.setAlignment(Qt.AlignCenter)
        or_label.setStyleSheet("color: #888888; font-weight: bold; font-size: 11px; padding: 0 15px;")
        separator_layout.addWidget(or_label, 0)
        
        separator_line2 = QWidget()
        separator_line2.setFixedHeight(1)
        separator_line2.setStyleSheet("background: linear-gradient(to right, transparent, #666666, transparent);")
        separator_layout.addWidget(separator_line2, 2)
        
        scroll_content_layout.addWidget(separator_widget)
        
        code_section = QWidget()
        code_section.setObjectName("connectionCodeSection")
        code_section_layout = QVBoxLayout(code_section)
        code_section_layout.setSpacing(10)
        code_section_layout.setContentsMargins(15, 15, 15, 15)
        
        code_section.setStyleSheet("""
            QWidget#connectionCodeSection {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                margin: 5px;
            }
        """)
        
        code_label = QLabel("🔢 Enter 6-Character Code:")
        code_label.setObjectName("connectionLabel")
        code_label.setStyleSheet("font-weight: bold; color: #ffffff; font-size: 12px;")
        code_section_layout.addWidget(code_label)
        
        self.connection_code_input = QLineEdit()
        self.connection_code_input.setObjectName("connectionCodeInput")
        self.connection_code_input.setPlaceholderText("ABCD12")
        self.connection_code_input.setMaxLength(6)
        self.connection_code_input.setMinimumHeight(40)
        self.connection_code_input.setAlignment(Qt.AlignCenter)
        self.connection_code_input.textChanged.connect(self.format_connection_code)
        self.connection_code_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.1);
                border: 2px solid rgba(255, 255, 255, 0.2);
                border-radius: 20px;
                padding: 8px 15px;
                color: white;
                font-size: 16px;
                font-weight: bold;
                letter-spacing: 3px;
                text-align: center;
            }
            QLineEdit:focus {
                border: 2px solid #667eea;
                background-color: rgba(255, 255, 255, 0.15);
            }
            QLineEdit::placeholder {
                color: rgba(255, 255, 255, 0.6);
                letter-spacing: 3px;
            }
        """)
        code_section_layout.addWidget(self.connection_code_input)
        
        self.connect_code_btn = QPushButton("🔢 Connect via Code")
        self.connect_code_btn.setObjectName("connectCodeButton")
        self.connect_code_btn.clicked.connect(self.connect_via_code)
        self.connect_code_btn.setMinimumHeight(45)
        self.connect_code_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                border: none;
                border-radius: 22px;
                color: white;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #778eeb, stop:1 #865bb3);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #556ee9, stop:1 #653b91);
            }
            QPushButton:disabled {
                background: #666666;
                color: #999999;
            }
        """)
        code_section_layout.addWidget(self.connect_code_btn)
        
        scroll_content_layout.addWidget(code_section)
        
        scroll_content_layout.addStretch()
        
        scroll_area.setWidget(scroll_content)
        
        self.setup_smooth_scrolling(scroll_area)
        
        link_layout.addWidget(scroll_area)
        
        connection_tabs.addTab(link_tab, "Link/Code")
        
        device_layout.addWidget(connection_tabs)
        layout.addWidget(device_group)
        
        transfer_group = QGroupBox("🚀 Transfer")
        transfer_group.setObjectName("transferGroup")
        transfer_layout = QVBoxLayout(transfer_group)
        transfer_layout.setSpacing(10)
        
        progress_label = QLabel("Transfer Progress:")
        progress_label.setObjectName("progressLabel")
        transfer_layout.addWidget(progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("transferProgress")
        self.progress_bar.setMinimumHeight(25)
        transfer_layout.addWidget(self.progress_bar)
        
        self.send_btn = QPushButton("🚀 Send Files")
        self.send_btn.setObjectName("sendButton")
        self.send_btn.clicked.connect(self.send_files)
        self.send_btn.setMinimumHeight(45)
        transfer_layout.addWidget(self.send_btn)
        
        layout.addWidget(transfer_group)
        
        self.tab_widget.addTab(send_widget, "Send Files")
    
    def create_receive_tab(self):
        """Create the receive files tab"""
        receive_widget = QWidget()
        layout = QVBoxLayout(receive_widget)
        
        status_group = QGroupBox("Receiver Status")
        status_layout = QVBoxLayout(status_group)
        
        self.receiver_status = QLabel("Stopped")
        self.receiver_status.setStyleSheet("color: red; font-weight: bold;")
        status_layout.addWidget(self.receiver_status)
        
        self.start_receiver_btn = QPushButton("Start Receiver")
        self.start_receiver_btn.clicked.connect(self.toggle_receiver)
        status_layout.addWidget(self.start_receiver_btn)
        
        layout.addWidget(status_group)
        
        sharing_group = QGroupBox("Share Connection")
        sharing_layout = QVBoxLayout(sharing_group)
        
        code_layout = QHBoxLayout()
        code_layout.addWidget(QLabel("Connection Code:"))
        self.connection_code_label = QLabel("------")
        self.connection_code_label.setStyleSheet("font-weight: bold; font-size: 14pt; color: #0078d4;")
        code_layout.addWidget(self.connection_code_label)
        
        self.copy_code_btn = QPushButton("Copy Code")
        self.copy_code_btn.clicked.connect(self.copy_connection_code)
        code_layout.addWidget(self.copy_code_btn)
        sharing_layout.addLayout(code_layout)
        
        sharing_layout.addWidget(QLabel("Connection Link:"))
        self.connection_link_display = QLineEdit()
        self.connection_link_display.setReadOnly(True)
        self.connection_link_display.setPlaceholderText("Start receiver to generate link")
        sharing_layout.addWidget(self.connection_link_display)
        
        link_buttons = QHBoxLayout()
        self.copy_link_btn = QPushButton("Copy Link")
        self.copy_link_btn.clicked.connect(self.copy_connection_link)
        self.regenerate_btn = QPushButton("Regenerate")
        self.regenerate_btn.clicked.connect(self.regenerate_connection)
        link_buttons.addWidget(self.copy_link_btn)
        link_buttons.addWidget(self.regenerate_btn)
        sharing_layout.addLayout(link_buttons)
        
        layout.addWidget(sharing_group)
        
        location_group = QGroupBox("Download Location")
        location_layout = QVBoxLayout(location_group)
        
        self.download_path = QLineEdit(os.path.expanduser("~/Downloads"))
        location_layout.addWidget(self.download_path)
        
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self.browse_download_location)
        location_layout.addWidget(self.browse_btn)
        
        layout.addWidget(location_group)
        
        received_group = QGroupBox("Received Files")
        received_layout = QVBoxLayout(received_group)
        
        self.received_list = QListWidget()
        received_layout.addWidget(self.received_list)
        
        layout.addWidget(received_group)
        
        self.tab_widget.addTab(receive_widget, "Receive Files")
    
    def create_settings_tab(self):
        """Create the settings tab"""
        settings_widget = QWidget()
        layout = QVBoxLayout(settings_widget)
        
        network_group = QGroupBox("Network Settings")
        network_layout = QVBoxLayout(network_group)
        
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Receiver Port:"))
        self.port_input = QLineEdit(str(self.config.RECEIVER_PORT))
        port_layout.addWidget(self.port_input)
        network_layout.addLayout(port_layout)
        
        discovery_layout = QHBoxLayout()
        discovery_layout.addWidget(QLabel("Discovery Port:"))
        self.discovery_port_input = QLineEdit(str(self.config.DISCOVERY_PORT))
        discovery_layout.addWidget(self.discovery_port_input)
        network_layout.addLayout(discovery_layout)
        
        layout.addWidget(network_group)
        
        security_group = QGroupBox("Security Settings")
        security_layout = QVBoxLayout(security_group)
        
        self.encryption_enabled = QPushButton("Encryption: Enabled")
        self.encryption_enabled.setCheckable(True)
        self.encryption_enabled.setChecked(True)
        security_layout.addWidget(self.encryption_enabled)
        
        layout.addWidget(security_group)
        
        self.save_settings_btn = QPushButton("Save Settings")
        self.save_settings_btn.clicked.connect(self.save_settings)
        layout.addWidget(self.save_settings_btn)
        
        self.tab_widget.addTab(settings_widget, "Settings")
    
    def create_log_tab(self):
        """Create the log tab"""
        log_widget = QWidget()
        layout = QVBoxLayout(log_widget)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
        log_controls = QHBoxLayout()
        self.clear_log_btn = QPushButton("Clear Log")
        self.clear_log_btn.clicked.connect(self.clear_log)
        log_controls.addWidget(self.clear_log_btn)
        
        layout.addLayout(log_controls)
        
        self.tab_widget.addTab(log_widget, "Logs")
        
        self.log_timer = QTimer()
        self.log_timer.timeout.connect(self.update_log)
        self.log_timer.start(1000)  # Update every second
    
    def init_backend(self):
        """Initialize backend services"""
        try:
            self.sender = FileSender(self.config)
            self.receiver = FileReceiver(self.config)
            self.discovery = DeviceDiscovery(self.config)
            self.log_message("Backend services initialized")
            
            self.connected_devices_timer.start(10000)  # Update every 10 seconds (reduced frequency)
            
        except Exception as e:
            self.log_message(f"Error initializing backend: {e}")
    
    def add_files(self):
        """Add files to send list"""
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files to Send")
        for file_path in files:
            self.file_list.addItem(file_path)
            self.log_message(f"Added file: {os.path.basename(file_path)}")
        
        if files:
            self.update_file_statistics()
    
    def remove_files(self):
        """Remove selected files from send list"""
        current_row = self.file_list.currentRow()
        
        if current_row >= 0:
            item = self.file_list.item(current_row)
            if item:
                file_name = os.path.basename(item.text())
                removed_item = self.file_list.takeItem(current_row)
                
                self.log_message(f"Removed file: {file_name}")
                
                self.update_file_statistics()
        else:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self, "No Selection", 
                                   "Please select a file from the list to remove.")
            self.log_message("Remove file failed: No file selected")
    
    def update_file_statistics(self):
        """Update file count and total size statistics"""
        try:
            file_count = self.file_list.count()
            total_size = 0
            
            for i in range(file_count):
                item = self.file_list.item(i)
                if item and os.path.exists(item.text()):
                    total_size += os.path.getsize(item.text())
            
            if total_size < 1024:
                size_str = f"{total_size} B"
            elif total_size < 1024 * 1024:
                size_str = f"{total_size / 1024:.1f} KB"
            elif total_size < 1024 * 1024 * 1024:
                size_str = f"{total_size / (1024 * 1024):.1f} MB"
            else:
                size_str = f"{total_size / (1024 * 1024 * 1024):.1f} GB"
            
            if file_count > 0:
                status_msg = f"📁 {file_count} file{'s' if file_count != 1 else ''} selected ({size_str})"
                self.update_status_message(status_msg)
            else:
                self.update_status_message("📁 No files selected")
                
        except Exception as e:
            self.log_message(f"Error updating file statistics: {e}")
    
    def refresh_devices(self):
        """Refresh available devices"""
        self.discovery_status.setText("🔄 Scanning for devices...")
        self.discovery_status.setStyleSheet("color: #0078d4; font-style: italic;")
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("🔄 Scanning...")
        
        manual_devices = []
        for i in range(self.device_list.count()):
            item_text = self.device_list.item(i).text()
            if "Manual Device" in item_text:
                manual_devices.append(item_text)
        
        self.device_list.clear()
        
        for device in manual_devices:
            item = QListWidgetItem(device)
            self.device_list.addItem(item)
        
        try:
            if self.discovery:
                print("🔍 Starting device discovery...")
                self.discovery_status.setText("🔍 Discovering devices on network...")
                
                if not self.discovery.listening:
                    self.discovery.start_listening()
                    time.sleep(0.5)  # Give listener time to start
                
                if not self.discovery.broadcasting:
                    self.discovery.start_broadcasting()
                    
                if not self.discovery_thread or not self.discovery_thread.isRunning():
                    self.discovery_thread = DiscoveryThread(self.discovery)
                    self.discovery_thread.device_found.connect(self.add_device)
                    self.discovery_thread.discovery_completed.connect(self.discovery_finished)
                    self.discovery_thread.start()
                    
                    QTimer.singleShot(10000, self.stop_discovery_scan)
            else:
                self.discovery_status.setText("❌ Discovery service not available")
                self.discovery_status.setStyleSheet("color: #dc3545; font-style: italic;")
                self.refresh_btn.setEnabled(True)
                self.refresh_btn.setText("🔄 Refresh Devices")
        except Exception as e:
            self.log_message(f"Error during device discovery: {e}")
            self.discovery_status.setText("❌ Discovery failed")
            self.discovery_status.setStyleSheet("color: #dc3545; font-style: italic;")
            self.refresh_btn.setEnabled(True)
            self.refresh_btn.setText("🔄 Refresh Devices")
    
    def discovery_finished(self):
        """Handle discovery completion"""
        self.log_message("Device discovery completed")
        
        self.ensure_discovery_scroll_works()
        QTimer.singleShot(100, self.ensure_discovery_scroll_works)
        QTimer.singleShot(300, self.ensure_discovery_scroll_works)
        
        discovered_count = 0
        for i in range(self.device_list.count()):
            if "Manual Device" not in self.device_list.item(i).text():
                discovered_count += 1
        
        if discovered_count > 0:
            self.discovery_status.setText(f"✅ Found {discovered_count} device{'s' if discovered_count != 1 else ''}")
            self.discovery_status.setStyleSheet("color: #28a745; font-style: italic;")
        else:
            self.discovery_status.setText("⚠️ No devices found - Try manual IP")
            self.discovery_status.setStyleSheet("color: #ffc107; font-style: italic;")
        
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("🔄 Refresh Devices")
    
    def stop_discovery_scan(self):
        """Stop the discovery scan"""
        if self.discovery_thread and self.discovery_thread.isRunning():
            self.discovery_thread.stop()
        
        discovered_count = 0
        for i in range(self.device_list.count()):
            if "Manual Device" not in self.device_list.item(i).text():
                discovered_count += 1
        
        total_count = self.device_list.count()
        
        if discovered_count > 0:
            self.discovery_status.setText(f"✅ Found {discovered_count} device(s) via discovery")
            self.discovery_status.setStyleSheet("color: #28a745; font-style: italic;")
        else:
            if total_count > 0:
                self.discovery_status.setText(f"⚠️ No new devices found ({total_count} manual)")
            else:
                self.discovery_status.setText("❌ No devices found - Try manual IP")
                self.device_list.addItem("No devices found - Use manual IP or check network")
            self.discovery_status.setStyleSheet("color: #dc3545; font-style: italic;")
        
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("🔄 Refresh Devices")
    
    def add_device(self, ip, name):
        """Add discovered device to list"""
        device_text = f"{name} ({ip})"
        for i in range(self.device_list.count()):
            if self.device_list.item(i).text() == device_text:
                return
        
        if self.device_list.count() == 1:
            first_item = self.device_list.item(0)
            if first_item and "No devices found" in first_item.text():
                self.device_list.clear()
        
        item = QListWidgetItem(device_text)
        self.device_list.addItem(item)
        
        device_info = {'name': name, 'ip': ip}
        self.add_connected_device(device_info, 'discovery')
        
        self.device_list.setCurrentItem(item)
        self.device_list.scrollToItem(item, QListWidget.EnsureVisible)
        
        self.ensure_discovery_scroll_works()
        
        try:
            if hasattr(self, 'discovery_scroll_area'):
                self.discovery_scroll_area.widget().adjustSize()
                self.discovery_scroll_area.updateGeometry()
                
                from PyQt5.QtWidgets import QApplication
                QApplication.processEvents()
                
                QTimer.singleShot(50, self.ensure_discovery_scroll_works)
                QTimer.singleShot(200, self.ensure_discovery_scroll_works)
                
                scroll_bar = self.discovery_scroll_area.verticalScrollBar()
                current_pos = scroll_bar.value()
                max_scroll = scroll_bar.maximum()
                
                if max_scroll > 0 and current_pos < (max_scroll * 0.7):  # If not in bottom 30%
                    target_pos = int(max_scroll * 0.8)  # Scroll to 80% down
                    scroll_bar.setValue(target_pos)
                else:
                    self.scroll_discovery_to_bottom()
        except Exception as e:
            print(f"Scroll update error: {e}")  # Debug info
    
    def add_manual_device(self):
        """Add device manually by IP address"""
        from PyQt5.QtWidgets import QInputDialog, QMessageBox
        
        instruction_msg = (
            "📱 Manual Device Connection\n\n"
            "To find your device's IP address:\n\n"
            "• Windows: Open Command Prompt → type 'ipconfig'\n"
            "• Android: Settings → About Phone → Status → IP Address\n"
            "• iPhone: Settings → Wi-Fi → Tap (i) next to network\n"
            "• Linux/Mac: Open Terminal → type 'ifconfig'\n\n"
            "Both devices must be on the same network!"
        )
        
        QMessageBox.information(self, "How to Find IP Address", instruction_msg)
        
        ip, ok = QInputDialog.getText(self, 'Manual Device Connection', 
                                     'Enter the target device IP address:\n(Example: 192.168.1.100)')
        if ok and ip.strip():
            ip = ip.strip()
            
            parts = ip.split('.')
            if len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts):
                self.log_message(f"Attempting manual connection to {ip}")
                self.discovery_status.setText(f"🔄 Testing connection to {ip}...")
                self.discovery_status.setStyleSheet("color: #0078d4; font-style: italic;")
                
                try:
                    if self.sender and hasattr(self.sender, '_test_connection'):
                        port = self.config.RECEIVER_PORT
                        self.log_message(f"Testing connection to {ip}:{port}")
                        
                        if self.sender._test_connection(ip, port, timeout=5):
                            device_name = f"Manual Device"
                            device_text = f"{device_name} ({ip})"
                            
                            exists = False
                            for i in range(self.device_list.count()):
                                item = self.device_list.item(i)
                                if item and ip in item.text():
                                    exists = True
                                    break
                            
                            if not exists:
                                if self.device_list.count() == 1:
                                    first_item = self.device_list.item(0)
                                    if first_item and "No devices found" in first_item.text():
                                        self.device_list.clear()
                                
                                item = QListWidgetItem(device_text)
                                self.device_list.addItem(item)
                                self.device_list.setCurrentItem(item)
                                
                                self.device_list.scrollToItem(item, QListWidget.EnsureVisible)
                                
                                try:
                                    if hasattr(self, 'discovery_scroll_area'):
                                        scroll_bar = self.discovery_scroll_area.verticalScrollBar()
                                        target_pos = int(scroll_bar.maximum() * 0.8)
                                        scroll_bar.setValue(target_pos)
                                except Exception:
                                    pass
                                
                                self.discovery_status.setText(f"✅ Connected to {ip}")
                                self.discovery_status.setStyleSheet("color: #28a745; font-style: italic;")
                                self.log_message(f"Successfully connected to manual device: {ip}")
                                
                                device_info = {'name': device_name, 'ip': ip}
                                self.add_connected_device(device_info, 'manual')
                                
                                QMessageBox.information(self, "Success", 
                                                      f"✅ Device at {ip} added successfully!\n\n"
                                                      f"Make sure Fshare receiver is running on that device.")
                            else:
                                self.discovery_status.setText(f"⚠️ Device {ip} already in list")
                                self.discovery_status.setStyleSheet("color: #ffc107; font-style: italic;")
                                QMessageBox.information(self, "Already Added", f"Device {ip} is already in your list.")
                        else:
                            self.discovery_status.setText(f"❌ Cannot connect to {ip}")
                            self.discovery_status.setStyleSheet("color: #dc3545; font-style: italic;")
                            self.log_message(f"Failed to connect to manual device: {ip}")
                            
                            error_msg = (
                                f"❌ Cannot connect to {ip}\n\n"
                                f"Please check:\n"
                                f"• Both devices are on the same Wi-Fi network\n"
                                f"• Fshare receiver is running on the target device\n"
                                f"• IP address is correct\n"
                                f"• Port {self.config.RECEIVER_PORT} is not blocked by firewall\n"
                                f"• No VPN is interfering with connection"
                            )
                            QMessageBox.warning(self, "Connection Failed", error_msg)
                    else:
                        device_name = f"Manual Device (Untested)"
                        device_text = f"{device_name} ({ip})"
                        
                        exists = False
                        for i in range(self.device_list.count()):
                            item = self.device_list.item(i)
                            if item and ip in item.text():
                                exists = True
                                break
                        
                        if not exists:
                            if self.device_list.count() == 1:
                                first_item = self.device_list.item(0)
                                if first_item and "No devices found" in first_item.text():
                                    self.device_list.clear()
                            
                            item = QListWidgetItem(device_text)
                            self.device_list.addItem(item)
                            self.device_list.setCurrentItem(item)
                            
                            self.device_list.scrollToItem(item, QListWidget.EnsureVisible)
                            
                            try:
                                if hasattr(self, 'discovery_scroll_area'):
                                    scroll_bar = self.discovery_scroll_area.verticalScrollBar()
                                    target_pos = int(scroll_bar.maximum() * 0.8)
                                    scroll_bar.setValue(target_pos)
                            except Exception:
                                pass
                                
                            self.discovery_status.setText(f"➕ Added {ip} (untested)")
                            self.discovery_status.setStyleSheet("color: #ffc107; font-style: italic;")
                            self.log_message(f"Added manual device (untested): {ip}")
                            
                            device_info = {'name': device_name, 'ip': ip}
                            self.add_connected_device(device_info, 'manual')
                            
                            QMessageBox.information(self, "Device Added", 
                                                  f"Device {ip} added to list.\n\n"
                                                  f"Connection test not available - make sure the receiver is running.")
                
                except Exception as e:
                    self.log_message(f"Error testing manual connection: {e}")
                    self.discovery_status.setText(f"❌ Error connecting to {ip}")
                    self.discovery_status.setStyleSheet("color: #dc3545; font-style: italic;")
                    QMessageBox.critical(self, "Connection Error", f"Error testing connection: {str(e)}")
                    
            else:
                QMessageBox.warning(self, "Invalid IP Address", 
                                   "Please enter a valid IP address.\n\n"
                                   "Example: 192.168.1.100\n"
                                   "Format: Four numbers (0-255) separated by dots.")
                self.log_message(f"Invalid IP address entered: {ip}")
    
    def send_files(self):
        """Send selected files to selected devices with device selection dialog"""
        if self.file_list.count() == 0:
            QMessageBox.warning(self, "No Files Selected", 
                               "Please add some files to send first.\n"
                               "Use the '📎 Add Files' button to select files.")
            return
        
        if not self.real_connected_devices:
            QMessageBox.warning(self, "No Connected Devices", 
                               "No devices are currently connected.\n\n"
                               "Please connect devices first using:\n"
                               "• 🔄 Auto Discovery (Refresh Devices)\n"
                               "• 📍 Manual IP address\n"
                               "• 🔢 6-digit connection code\n"
                               "• 🔗 Connection link")
            return
        
        selected_devices = self.show_device_selection_dialog()
        
        if not selected_devices:
            return  # User cancelled or no devices selected
        
        file_count = self.file_list.count()
        file_list = [self.file_list.item(i).text() for i in range(file_count)]
        
        device_list_str = "\n".join([f"📱 {dev['name']} ({dev['ip']}) - {dev['status'].upper()}" for dev in selected_devices])
        
        reply = QMessageBox.question(self, "Confirm File Transfer", 
            f"Send {file_count} file(s) to {len(selected_devices)} device(s):\n\n"
            f"{device_list_str}\n\n"
            f"Files to send:\n" + 
            "\n".join([f"• {os.path.basename(f)}" for f in file_list[:5]]) +
            (f"\n... and {file_count-5} more files" if file_count > 5 else ""),
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.Yes)
        
        if reply == QMessageBox.Yes:
            self.start_multi_device_transfer(selected_devices, file_list)
    
    def show_device_selection_dialog(self):
        """Show device selection dialog for file transfer"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QScrollArea
        
        dialog = QDialog(self)
        dialog.setWindowTitle("🚀 Select Devices for File Transfer")
        dialog.setModal(True)
        dialog.resize(500, 400)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title_label = QLabel("📱 Select devices to receive files:")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #ffffff;
                padding: 10px;
                background-color: rgba(79, 172, 254, 0.2);
                border-radius: 8px;
                border-left: 4px solid #4facfe;
            }
        """)
        layout.addWidget(title_label)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: 2px solid rgba(79, 172, 254, 0.3);
                border-radius: 10px;
                background-color: rgba(255, 255, 255, 0.05);
            }
        """)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(8)
        
        device_checkboxes = []
        connected_count = 0
        disconnected_count = 0
        
        for device_key, device_data in self.real_connected_devices.items():
            device_name = device_data['name']
            device_ip = device_data['ip']
            device_status = device_data['status']
            connection_method = device_data['method']
            
            status_icon = '🟢' if device_status == 'connected' else '🟡'
            method_icon = {'link': '🔗', 'code': '🔢', 'discovery': '📱', 'manual': '🔧'}.get(connection_method, '📱')
            
            checkbox = QCheckBox(f"{status_icon} {method_icon} {device_name} ({device_ip})")
            checkbox.setStyleSheet("""
                QCheckBox {
                    font-size: 13px;
                    color: white;
                    padding: 10px 15px;
                    background-color: rgba(255, 255, 255, 0.08);
                    border-radius: 8px;
                    margin: 2px;
                }
                QCheckBox:hover {
                    background-color: rgba(79, 172, 254, 0.15);
                }
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                }
                QCheckBox::indicator:unchecked {
                    border: 2px solid #666666;
                    border-radius: 3px;
                    background-color: rgba(255, 255, 255, 0.1);
                }
                QCheckBox::indicator:checked {
                    border: 2px solid #4facfe;
                    border-radius: 3px;
                    background-color: #4facfe;
                    image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAiIGhlaWdodD0iOCIgdmlld0JveD0iMCAwIDEwIDgiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik04LjUgMUwzLjUgNkwxLjUgNCIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4KPC9zdmc+);
                }
            """)
            
            checkbox.device_data = device_data
            
            if device_status == 'connected':
                checkbox.setEnabled(True)
                connected_count += 1
            else:
                checkbox.setEnabled(False)
                checkbox.setToolTip("Device is currently disconnected")
                disconnected_count += 1
            
            device_checkboxes.append(checkbox)
            scroll_layout.addWidget(checkbox)
        
        if connected_count == 0:
            no_devices_label = QLabel("❌ No connected devices available")
            no_devices_label.setStyleSheet("color: #dc3545; font-style: italic; padding: 20px; text-align: center;")
            scroll_layout.addWidget(no_devices_label)
        else:
            status_label = QLabel(f"✅ {connected_count} device(s) available" + 
                                (f" • {disconnected_count} disconnected" if disconnected_count > 0 else ""))
            status_label.setStyleSheet("color: #28a745; font-size: 11px; font-style: italic; padding: 10px;")
            scroll_layout.addWidget(status_label)
        
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        
        controls_layout = QHBoxLayout()
        
        select_all_btn = QPushButton("✅ Select All Connected")
        select_all_btn.clicked.connect(lambda: self.select_all_connected_devices(device_checkboxes))
        select_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                border: none;
                border-radius: 6px;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #34ce57; }
            QPushButton:pressed { background-color: #1e7e34; }
        """)
        controls_layout.addWidget(select_all_btn)
        
        clear_all_btn = QPushButton("❌ Clear All")
        clear_all_btn.clicked.connect(lambda: self.clear_all_device_selection(device_checkboxes))
        clear_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                border: none;
                border-radius: 6px;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #e74c3c; }
            QPushButton:pressed { background-color: #c82333; }
        """)
        controls_layout.addWidget(clear_all_btn)
        
        layout.addLayout(controls_layout)
        
        button_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("❌ Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                border: none;
                border-radius: 8px;
                color: white;
                font-weight: bold;
                padding: 12px 24px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #7c828d; }
            QPushButton:pressed { background-color: #5a6268; }
        """)
        button_layout.addWidget(cancel_btn)
        
        send_btn = QPushButton("🚀 Send to Selected Devices")
        send_btn.clicked.connect(dialog.accept)
        send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4facfe, stop:1 #00f2fe);
                border: none;
                border-radius: 8px;
                color: white;
                font-weight: bold;
                padding: 12px 24px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5fbdff, stop:1 #1ff3ff);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3f9cfe, stop:1 #00e2ee);
            }
        """)
        button_layout.addWidget(send_btn)
        
        layout.addLayout(button_layout)
        
        dialog.setStyleSheet("""
            QDialog {
                background-color: #1a1a2e;
                color: white;
            }
        """)
        
        if dialog.exec_() == QDialog.Accepted:
            selected_devices = []
            for checkbox in device_checkboxes:
                if checkbox.isChecked() and checkbox.isEnabled():
                    selected_devices.append(checkbox.device_data)
            return selected_devices
        else:
            return None
    
    def select_all_connected_devices(self, device_checkboxes):
        """Select all connected devices in the dialog"""
        for checkbox in device_checkboxes:
            if checkbox.isEnabled():  # Only connected devices
                checkbox.setChecked(True)
    
    def clear_all_device_selection(self, device_checkboxes):
        """Clear all device selections in the dialog"""
        for checkbox in device_checkboxes:
            checkbox.setChecked(False)
    
    def show_connected_device_context_menu(self, position):
        """Show context menu for connected devices list"""
        from PyQt5.QtWidgets import QMenu
        
        item = self.connected_devices_list.itemAt(position)
        if not item or not hasattr(item, 'data') or not item.data(Qt.UserRole):
            return
        
        device_data = item.data(Qt.UserRole)
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2d2d30;
                border: 1px solid #4facfe;
                border-radius: 6px;
                color: white;
                font-size: 12px;
            }
            QMenu::item {
                padding: 8px 16px;
                background-color: transparent;
            }
            QMenu::item:selected {
                background-color: rgba(79, 172, 254, 0.3);
            }
        """)
        
        test_action = menu.addAction("🔍 Test Connection")
        test_action.triggered.connect(lambda: self.test_device_connection(device_data))
        
        remove_action = menu.addAction("❌ Remove Device")
        remove_action.triggered.connect(lambda: self.remove_connected_device(device_data))
        
        send_action = menu.addAction("🚀 Send Files to This Device")
        send_action.triggered.connect(lambda: self.send_files_to_specific_device(device_data))
        
        info_action = menu.addAction("ℹ️ Device Information")
        info_action.triggered.connect(lambda: self.show_device_info(device_data))
        
        menu.exec_(self.connected_devices_list.mapToGlobal(position))
    
    def test_device_connection(self, device_data):
        """Test connection to a specific device"""
        device_name = device_data['name']
        device_ip = device_data['ip']
        
        self.log_message(f"Testing connection to {device_name} ({device_ip})")
        
        try:
            import socket
            from threading import Timer
            
            def test_connection():
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(3)  # 3 second timeout
                    result = sock.connect_ex((device_ip, self.config.RECEIVER_PORT))
                    sock.close()
                    return result == 0
                except Exception:
                    return False
            
            is_connected = test_connection()
            
            if is_connected:
                QMessageBox.information(self, "Connection Test", 
                                      f"✅ Successfully connected to {device_name}\n\n"
                                      f"IP: {device_ip}\n"
                                      f"Status: Online and reachable")
                device_data['status'] = 'connected'
                device_data['timestamp'] = time.time()
                device_data['last_verified'] = time.time()  # Mark as recently verified
            else:
                QMessageBox.warning(self, "Connection Test", 
                                   f"❌ Cannot reach {device_name}\n\n"
                                   f"IP: {device_ip}\n"
                                   f"Status: Offline or unreachable\n\n"
                                   f"Possible causes:\n"
                                   f"• Device is turned off or sleeping\n"
                                   f"• Fshare receiver is not running\n"
                                   f"• Network connectivity issues\n"
                                   f"• Firewall blocking the connection")
                device_data['status'] = 'disconnected'
            
            self.refresh_connected_devices_display()
            
        except Exception as e:
            QMessageBox.critical(self, "Connection Test Error", 
                               f"Error testing connection to {device_name}:\n{str(e)}\n\n"
                               f"This might be due to network issues or firewall restrictions.")
            self.log_message(f"Connection test failed for {device_name}: {e}")
    
    def remove_connected_device(self, device_data):
        """Remove a device from connected devices list"""
        device_name = device_data['name']
        device_ip = device_data['ip']
        
        reply = QMessageBox.question(self, "Remove Device", 
                                    f"Remove {device_name} ({device_ip}) from connected devices?\n\n"
                                    f"You can always reconnect later using the same method.",
                                    QMessageBox.Yes | QMessageBox.No, 
                                    QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            device_key = f"{device_name}_{device_ip}"
            if device_key in self.real_connected_devices:
                del self.real_connected_devices[device_key]
                self.refresh_connected_devices_display()
                self.log_message(f"Removed device: {device_name} ({device_ip})")
                QMessageBox.information(self, "Device Removed", f"Device {device_name} has been removed from connected devices.")
    
    def send_files_to_specific_device(self, device_data):
        """Send files to a specific device"""
        if self.file_list.count() == 0:
            QMessageBox.warning(self, "No Files Selected", 
                               "Please add some files to send first.\n"
                               "Use the '📎 Add Files' button to select files.")
            return
        
        device_name = device_data['name']
        device_ip = device_data['ip']
        device_status = device_data['status']
        
        if device_status != 'connected':
            reply = QMessageBox.question(self, "Device Disconnected", 
                                        f"Device {device_name} appears to be disconnected.\n\n"
                                        f"Do you want to try sending files anyway?",
                                        QMessageBox.Yes | QMessageBox.No, 
                                        QMessageBox.No)
            if reply == QMessageBox.No:
                return
        
        file_count = self.file_list.count()
        file_list = [self.file_list.item(i).text() for i in range(file_count)]
        
        reply = QMessageBox.question(self, "Confirm File Transfer", 
                                    f"Send {file_count} file(s) to {device_name}?\n\n"
                                    f"Device: {device_name} ({device_ip})\n"
                                    f"Status: {device_status.upper()}\n\n"
                                    f"Files to send:\n" + 
                                    "\n".join([f"• {os.path.basename(f)}" for f in file_list[:5]]) +
                                    (f"\n... and {file_count-5} more files" if file_count > 5 else ""),
                                    QMessageBox.Yes | QMessageBox.No, 
                                    QMessageBox.Yes)
        
        if reply == QMessageBox.Yes:
            self.start_multi_device_transfer([device_data], file_list)
    
    def show_device_info(self, device_data):
        """Show detailed information about a connected device"""
        device_name = device_data['name']
        device_ip = device_data['ip']
        device_status = device_data['status']
        connection_method = device_data['method']
        connect_time = device_data['timestamp']
        
        import datetime
        connect_datetime = datetime.datetime.fromtimestamp(connect_time)
        time_connected = datetime.datetime.now() - connect_datetime
        
        method_icons = {'link': '🔗 Link', 'code': '🔢 Code', 'discovery': '📱 Discovery', 'manual': '🔧 Manual'}
        method_display = method_icons.get(connection_method, '📱 Discovery')
        
        info_text = f"""
<h3>📱 Device Information</h3>

<b>Device Name:</b> {device_name}<br>
<b>IP Address:</b> {device_ip}<br>
<b>Connection Status:</b> <span style="color: {'green' if device_status == 'connected' else 'orange'}">{device_status.upper()}</span><br>
<b>Connection Method:</b> {connection_method.upper()}<br>
<b>Connected Since:</b> {connect_datetime.strftime('%Y-%m-%d %H:%M:%S')}<br>
<b>Time Connected:</b> {str(time_connected).split('.')[0]}<br>

<h4>Connection Details:</h4>
• <b>Method Icon:</b> {method_display}<br>
• <b>Status Icon:</b> {'🟢 Online' if device_status == 'connected' else '🟡 Offline'}<br>
• <b>Network:</b> Same Wi-Fi network required<br>

<h4>Available Actions:</h4>
• Right-click on device for more options<br>
• Test connection status<br>
• Send files directly to this device<br>
• Remove from connected devices list<br>
        """
        
        info_dialog = QMessageBox(self)
        info_dialog.setWindowTitle(f"Device Info - {device_name}")
        info_dialog.setTextFormat(Qt.RichText)
        info_dialog.setText(info_text)
        info_dialog.setIcon(QMessageBox.Information)
        info_dialog.setStandardButtons(QMessageBox.Ok)
        info_dialog.exec_()
    
    def start_multi_device_transfer(self, selected_devices, file_list):
        """Start file transfer to multiple devices with multiple files"""
        try:
            if not selected_devices:
                QMessageBox.warning(self, "No Devices Selected", "No devices selected for transfer.")
                return
            
            if not file_list:
                QMessageBox.warning(self, "No Files Selected", "No files selected for transfer.")
                return
            
            total_transfers = len(selected_devices) * len(file_list)
            device_names = [f"{dev['name']} ({dev['ip']})" for dev in selected_devices]
            file_names = [os.path.basename(f) for f in file_list]
            
            self.log_message(f"Starting multi-device transfer: {len(file_list)} files to {len(selected_devices)} devices ({total_transfers} total transfers)")
            self.log_message(f"Devices: {', '.join(device_names)}")
            self.log_message(f"Files: {', '.join(file_names)}")
            
            self.send_btn.setEnabled(False)
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(True)
            self.statusBar().showMessage(f"Transferring {len(file_list)} files to {len(selected_devices)} devices...")
            
            self.transfer_thread = TransferThread(self.sender, file_list, selected_devices)
            self.transfer_thread.progress_updated.connect(self.progress_bar.setValue)
            self.transfer_thread.transfer_completed.connect(self.multi_transfer_completed)
            self.transfer_thread.file_completed.connect(self.file_transfer_status)
            self.transfer_thread.start()
                
        except Exception as e:
            QMessageBox.critical(self, "Multi-Device Transfer Error", 
                               f"Error starting multi-device transfer:\n{str(e)}")
            self.log_message(f"Multi-device transfer initiation failed: {e}")
            self.send_btn.setEnabled(True)
            self.progress_bar.setVisible(False)
    
    def file_transfer_status(self, file_name, success, message):
        """Handle individual file transfer status updates"""
        self.log_message(message)
    
    def multi_transfer_completed(self, success, summary):
        """Handle multi-device transfer completion"""
        self.send_btn.setEnabled(True)
        self.progress_bar.setValue(100 if success else 0)
        self.progress_bar.setVisible(False)
        
        status_msg = "✅ All transfers completed successfully" if success else "⚠️ Some transfers failed"
        self.statusBar().showMessage(status_msg)
        self.log_message(f"Multi-device transfer completed: {status_msg}")
        
        result_dialog = QMessageBox(self)
        result_dialog.setWindowTitle("🚀 Transfer Results")
        result_dialog.setText("Multi-device file transfer completed!")
        result_dialog.setDetailedText(summary)
        result_dialog.setIcon(QMessageBox.Information if success else QMessageBox.Warning)
        result_dialog.setStandardButtons(QMessageBox.Ok)
        result_dialog.exec_()
    
    def start_transfer(self, file_path, target_ip):
        """Start single file transfer (legacy method, now uses multi-transfer system)"""
        target_device = {'ip': target_ip, 'name': f"Device-{target_ip}"}
        self.start_multi_device_transfer([target_device], [file_path])
    
    def transfer_completed(self, success, message):
        """Handle transfer completion (legacy method for backward compatibility)"""
        self.multi_transfer_completed(success, message)
    
    def toggle_receiver(self):
        """Start/stop receiver service"""
        if self.receiver and hasattr(self.receiver, 'running') and self.receiver.running:
            self.receiver.stop()
            self.receiver_status.setText("Stopped")
            self.receiver_status.setStyleSheet("color: red; font-weight: bold;")
            self.start_receiver_btn.setText("Start Receiver")
            self.connection_code_label.setText("------")
            self.connection_link_display.setText("")
            
            if self.discovery and self.discovery.broadcasting:
                self.discovery.stop_broadcasting()
            
            self.log_message("Receiver stopped - Device no longer visible to senders")
        else:
            try:
                self.receiver.download_path = self.download_path.text()
                self.receiver.start()
                self.receiver_status.setText("Running")
                self.receiver_status.setStyleSheet("color: green; font-weight: bold;")
                self.start_receiver_btn.setText("Stop Receiver")
                
                if self.discovery:
                    if not self.discovery.listening:
                        self.discovery.start_listening()
                    if not self.discovery.broadcasting:
                        self.discovery.start_broadcasting()
                        self.log_message("Broadcasting started - Device now visible to senders")
                
                self.update_connection_display()
                
                self.log_message(f"Receiver started on port {self.config.RECEIVER_PORT}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to start receiver: {e}")
                self.log_message(f"Failed to start receiver: {e}")
    
    def update_connection_display(self):
        """Update the connection code and link display"""
        if self.receiver and hasattr(self.receiver, 'running') and self.receiver.running:
            connection_info = self.receiver.get_connection_info()
            if connection_info:
                self.connection_code_label.setText(connection_info['code'])
                self.connection_link_display.setText(connection_info['link'])
    
    def copy_connection_code(self):
        """Copy connection code to clipboard"""
        code = self.connection_code_label.text()
        if code and code != "------":
            clipboard = QApplication.clipboard()
            clipboard.setText(code)
            QMessageBox.information(self, "Copied", f"Connection code '{code}' copied to clipboard!")
        else:
            QMessageBox.warning(self, "Warning", "No connection code available. Start the receiver first.")
    
    def copy_connection_link(self):
        """Copy connection link to clipboard"""
        link = self.connection_link_display.text()
        if link:
            clipboard = QApplication.clipboard()
            clipboard.setText(link)
            QMessageBox.information(self, "Copied", "Connection link copied to clipboard!")
        else:
            QMessageBox.warning(self, "Warning", "No connection link available. Start the receiver first.")
    
    def regenerate_connection(self):
        """Regenerate connection code and link"""
        if self.receiver and hasattr(self.receiver, 'running') and self.receiver.running:
            connection_info = self.receiver.regenerate_connection_code()
            if connection_info:
                self.connection_code_label.setText(connection_info['code'])
                self.connection_link_display.setText(connection_info['link'])
                QMessageBox.information(self, "Regenerated", "New connection code and link generated!")
        else:
            QMessageBox.warning(self, "Warning", "Receiver must be running to regenerate connection info.")
    
    def connect_via_link(self):
        """Connect to device using connection link"""
        link = self.connection_link_input.text().strip()
        if not link:
            QMessageBox.warning(self, "Warning", "Please enter a connection link")
            return
        
        if not link.startswith('fshare://connect/'):
            QMessageBox.warning(self, "Invalid Link", 
                               "Please enter a valid Fshare connection link.\n\n"
                               "Expected format:\n"
                               "fshare://connect/[IP]:[PORT]/[CODE]\n\n"
                               "Example:\n"
                               "fshare://connect/192.168.1.100:8080/ABC123")
            return
        
        self.connect_link_btn.setEnabled(False)
        self.connect_link_btn.setText("🔄 Connecting...")
        self.log_message(f"Attempting to connect via link...")
        
        try:
            if not self.sender:
                QMessageBox.critical(self, "Error", "Sender not initialized")
                return
            
            if self.discovery:
                if not self.discovery.listening:
                    self.discovery.start_listening()
                    time.sleep(0.5)
                    
                if not self.discovery.broadcasting:
                    self.discovery.start_broadcasting()
                    
                time.sleep(1)
                
            self.log_message("Parsing connection link...")
            connection_info = self.sender.connect_via_link(link)
            
            if connection_info:
                device_text = f"{connection_info['name']} ({connection_info['ip']})"
                existing_found = False
                
                for i in range(self.device_list.count()):
                    item = self.device_list.item(i)
                    if item and connection_info['ip'] in item.text():
                        existing_found = True
                        self.device_list.setCurrentRow(i)  # Use setCurrentRow for QListWidget
                        break
                
                if not existing_found:
                    self.device_list.addItem(device_text)
                    self.device_list.setCurrentRow(self.device_list.count() - 1)  # Select the newly added item
                
                self.add_connected_device(connection_info, 'link')
                
                success_msg = (
                    f"✅ Successfully connected!\n\n"
                    f"📱 Device: {connection_info['name']}\n"
                    f"🌐 IP Address: {connection_info['ip']}\n"
                    f"🎫 Connection Code: {connection_info.get('code', 'N/A')}\n\n"
                    f"You can now send files to this device."
                )
                QMessageBox.information(self, "Connection Successful", success_msg)
                self.connection_link_input.clear()
                self.log_message(f"Successfully connected to {connection_info['name']} ({connection_info['ip']}) via link")
            else:
                error_msg = (
                    f"❌ Connection failed using the provided link\n\n"
                    f"Troubleshooting tips:\n"
                    f"• Make sure the link is correct and complete\n"
                    f"• Ensure both devices are on the same Wi-Fi network\n"
                    f"• Check that Fshare receiver is running on the target device\n"
                    f"• Verify the target device is reachable\n"
                    f"• Try refreshing the device list first\n"
                    f"• The link might have expired - request a new one"
                )
                QMessageBox.warning(self, "Connection Failed", error_msg)
                self.log_message(f"Connection via link failed - device not reachable")
                
        except Exception as e:
            error_detail = str(e)
            self.log_message(f"Error during link connection: {error_detail}")
            QMessageBox.critical(self, "Connection Error", 
                               f"Error connecting via link:\n\n{error_detail}\n\n"
                               "Please check your network connection and try again.")
        finally:
            self.connect_link_btn.setEnabled(True)
            self.connect_link_btn.setText("🔗 Connect via Link")
    
    def show_device_help(self):
        """Show help dialog for device discovery and connection"""
        help_text = """
<h3>🔍 Device Discovery & Connection Guide</h3>

<h4>📊 Auto Discovery:</h4>
• Click <b>🔄 Refresh Devices</b> to scan for nearby devices
• Devices must be on the same Wi-Fi network
• Make sure Fshare receiver is running on target device
• Wait 5-10 seconds for devices to appear

<h4>📍 Manual IP Connection:</h4>
• Use when auto discovery doesn't find your device
• Enter IP address manually (e.g., 192.168.1.100)
• Check device's network settings for IP address
• Useful for devices with static IP addresses

<h4>🎫 Connect via Code:</h4>
• Each device shows a 6-digit connection code
• Enter the code from target device (e.g., ABCD12)
• Works across different network segments
• Code updates automatically when device restarts

<h4>🔗 Connect via Link:</h4>
• Share connection links between devices
• Format: fshare://connect/[IP]:[PORT]/[CODE]
• Can be shared via chat, email, or QR code
• Links include all connection information

<h4>🛠 Troubleshooting:</h4>
• <b>No devices found:</b> Check Wi-Fi connection, try manual IP
• <b>Connection fails:</b> Verify target device is running Fshare
• <b>Code doesn't work:</b> Make sure it's exactly 6 characters
• <b>IP not working:</b> Check if device is reachable (ping test)

<h4>💡 Tips for Success:</h4>
• Both devices should be on same network
• Keep receiver app running on target device
• Try refreshing if devices don't appear immediately
• Use manual IP as backup method
• Connection codes change each session
        """
        
        help_dialog = QMessageBox(self)
        help_dialog.setWindowTitle("Device Connection Help")
        help_dialog.setTextFormat(Qt.RichText)
        help_dialog.setText(help_text)
        help_dialog.setIcon(QMessageBox.Information)
        help_dialog.setStandardButtons(QMessageBox.Ok)
        help_dialog.exec_()
    
    def connect_via_code(self):
        """Connect to device using connection code"""
        code = self.connection_code_input.text().strip().upper()
        if not code:
            QMessageBox.warning(self, "Warning", "Please enter a 6-character connection code")
            return
        
        if len(code) != 6:
            QMessageBox.warning(self, "Invalid Code", 
                               "Connection code must be exactly 6 characters.\n"
                               "Example: ABCD12")
            return
        
        if not code.isalnum():
            QMessageBox.warning(self, "Invalid Code", 
                               "Connection code must contain only letters and numbers.\n"
                               "Example: ABCD12")
            return
        
        self.connect_code_btn.setEnabled(False)
        self.connect_code_btn.setText("🔍 Searching...")
        self.log_message(f"Attempting to connect using code: {code}")
        
        try:
            if not self.sender:
                QMessageBox.critical(self, "Error", "Sender not initialized")
                return
            
            if self.discovery:
                if not self.discovery.listening:
                    self.discovery.start_listening()
                    time.sleep(0.5)
                    
                if not self.discovery.broadcasting:
                    self.discovery.start_broadcasting()
                    
                time.sleep(2)
            
            self.log_message("Searching for device with matching code...")
            connection_info = self.sender.connect_via_code(code)
            
            if connection_info:
                device_text = f"{connection_info['name']} ({connection_info['ip']})"
                existing_found = False
                
                for i in range(self.device_list.count()):
                    item = self.device_list.item(i)
                    if item and connection_info['ip'] in item.text():
                        existing_found = True
                        self.device_list.setCurrentRow(i)  # Use setCurrentRow for QListWidget
                        break
                
                if not existing_found:
                    self.device_list.addItem(device_text)
                    self.device_list.setCurrentRow(self.device_list.count() - 1)  # Select the newly added item
                
                self.add_connected_device(connection_info, 'code')
                
                success_msg = (
                    f"✅ Successfully connected!\n\n"
                    f"📱 Device: {connection_info['name']}\n"
                    f"🌐 IP Address: {connection_info['ip']}\n"
                    f"🎫 Connection Code: {code}\n\n"
                    f"You can now send files to this device."
                )
                QMessageBox.information(self, "Device Found", success_msg)
                self.connection_code_input.clear()
                self.log_message(f"Successfully connected to {connection_info['name']} ({connection_info['ip']}) via code {code}")
            else:
                error_msg = (
                    f"❌ No device found with code '{code}'\n\n"
                    f"Troubleshooting tips:\n"
                    f"• Make sure the code is correct\n"
                    f"• Ensure both devices are on the same Wi-Fi network\n"
                    f"• Check that Fshare receiver is running on the target device\n"
                    f"• Try refreshing the device list first\n"
                    f"• Verify the target device shows the same 6-digit code"
                )
                QMessageBox.warning(self, "Device Not Found", error_msg)
                self.log_message(f"No device found with connection code: {code}")
                
        except Exception as e:
            error_detail = str(e)
            self.log_message(f"Error during code connection: {error_detail}")
            QMessageBox.critical(self, "Connection Error", 
                               f"Error searching for device:\n\n{error_detail}\n\n"
                               f"Please check your network connection and try again.")
        finally:
            self.connect_code_btn.setEnabled(True)
            self.connect_code_btn.setText("🔢 Connect via Code")
    
    def format_connection_code(self):
        """Format connection code input (uppercase and limit to 6 chars)"""
        text = self.connection_code_input.text().upper()
        formatted_text = ''.join(c for c in text if c.isalnum())
        if len(formatted_text) > 6:
            formatted_text = formatted_text[:6]
        
        cursor_position = self.connection_code_input.cursorPosition()
        self.connection_code_input.setText(formatted_text)
        if cursor_position <= len(formatted_text):
            self.connection_code_input.setCursorPosition(cursor_position)
    
    def browse_download_location(self):
        """Browse for download location"""
        directory = QFileDialog.getExistingDirectory(self, "Select Download Directory")
        if directory:
            self.download_path.setText(directory)
    
    def save_settings(self):
        """Save application settings"""
        try:
            self.config.RECEIVER_PORT = int(self.port_input.text())
            self.config.DISCOVERY_PORT = int(self.discovery_port_input.text())
            QMessageBox.information(self, "Success", "Settings saved successfully")
            self.log_message("Settings saved")
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid port number")
    
    def clear_log(self):
        """Clear log display"""
        self.log_text.clear()
    
    def update_log(self):
        """Update log display from log file"""
        try:
            log_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs', 'transfer.log')
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    if content != self.log_text.toPlainText():
                        self.log_text.setPlainText(content)
                        cursor = self.log_text.textCursor()
                        cursor.movePosition(cursor.End)
                        self.log_text.setTextCursor(cursor)
        except Exception:
            pass  # Ignore log reading errors
    
    def log_message(self, message):
        """Add message to log with Unicode safety"""
        try:
            import logging
            logger = logging.getLogger(__name__)
            
            safe_message = str(message)
            
            try:
                logger.info(safe_message)
            except UnicodeEncodeError:
                ascii_safe_message = safe_message.encode('ascii', errors='replace').decode('ascii')
                logger.info(f"[Unicode message converted] {ascii_safe_message}")
                
        except Exception as e:
            print(f"Logging failed: {e}. Message: {message}")
    
    def closeEvent(self, event):
        """Handle application close"""
        try:
            if hasattr(self, 'connected_devices_timer') and self.connected_devices_timer:
                self.connected_devices_timer.stop()
                self.log_message("Stopped connected devices monitoring")
            
            if self.receiver and hasattr(self.receiver, 'running') and self.receiver.running:
                self.receiver.stop()
            
            if self.discovery_thread and self.discovery_thread.isRunning():
                self.discovery_thread.stop()
                self.discovery_thread.wait(3000)  # Wait max 3 seconds
            
            if self.transfer_thread and self.transfer_thread.isRunning():
                self.transfer_thread.wait(3000)  # Wait max 3 seconds
            
            if hasattr(self, 'real_connected_devices'):
                self.real_connected_devices.clear()
            
            self.log_message("Application closing - all services stopped")
            
        except Exception as e:
            self.log_message(f"Error during application close: {e}")
        finally:
            event.accept()
    
    def create_status_bar(self):
        """Create modern status bar"""
        status_widget = QWidget()
        status_widget.setObjectName("statusWidget")
        status_widget.setFixedHeight(35)
        
        status_layout = QHBoxLayout(status_widget)
        status_layout.setContentsMargins(20, 5, 20, 5)
        
        self.status_message = QLabel("Ready")
        self.status_message.setObjectName("statusMessage")
        status_layout.addWidget(self.status_message)
        
        status_layout.addStretch()
        
        self.status_progress = QProgressBar()
        self.status_progress.setObjectName("statusProgress")
        self.status_progress.setFixedWidth(200)
        self.status_progress.setVisible(False)
        status_layout.addWidget(self.status_progress)
        
        self.stats_label = QLabel("Files: 0 | Size: 0 B")
        self.stats_label.setObjectName("statsLabel")
        status_layout.addWidget(self.stats_label)
        
        self.layout().addWidget(status_widget)
    
    def setup_animations(self):
        """Set up UI animations and effects"""
        from PyQt5.QtCore import QPropertyAnimation, QEasingCurve
        
        self.tab_animation = QPropertyAnimation(self.tab_widget, b"geometry")
        self.tab_animation.setDuration(300)
        self.tab_animation.setEasingCurve(QEasingCurve.OutCubic)
    
    def update_connection_status(self, connected):
        """Update connection status indicator"""
        if connected:
            self.connection_status.setStyleSheet("QLabel { color: #28a745; }")
            self.connection_status.setToolTip("Connected")
        else:
            self.connection_status.setStyleSheet("QLabel { color: #dc3545; }")
            self.connection_status.setToolTip("Disconnected")
    
    def update_status_message(self, message, show_progress=False, progress_value=0):
        """Update status bar message"""
        self.status_message.setText(message)
        self.status_progress.setVisible(show_progress)
        if show_progress:
            self.status_progress.setValue(progress_value)
    
    def update_statistics(self, files_count, total_size):
        """Update statistics display"""
        size_str = format_file_size(total_size) if 'format_file_size' in globals() else f"{total_size} B"
        self.stats_label.setText(f"Files: {files_count} | Size: {size_str}")
    
    def setup_smooth_scrolling(self, scroll_area):
        """Setup smooth scrolling for scroll area"""
        from PyQt5.QtCore import QPropertyAnimation, QEasingCurve, pyqtSignal
        from PyQt5.QtWidgets import QScrollBar
        
        scroll_bar = scroll_area.verticalScrollBar()
        
        self.scroll_animation = QPropertyAnimation(scroll_bar, b"value")
        self.scroll_animation.setDuration(300)
        self.scroll_animation.setEasingCurve(QEasingCurve.OutCubic)
        
        original_wheel_event = scroll_area.wheelEvent
        
        def smooth_wheel_event(event):
            angle_delta = event.angleDelta().y()
            steps = angle_delta / 120  # Standard wheel step
            current_value = scroll_bar.value()
            target_value = current_value - (steps * 50)  # 50 pixels per step
            
            target_value = max(scroll_bar.minimum(), min(scroll_bar.maximum(), target_value))
            
            self.scroll_animation.stop()
            self.scroll_animation.setStartValue(current_value)
            self.scroll_animation.setEndValue(target_value)
            self.scroll_animation.start()
            
            event.accept()
        
        scroll_area.wheelEvent = smooth_wheel_event
    
    def setup_enhanced_smooth_scrolling(self, scroll_area):
        """Setup enhanced smooth scrolling specifically for discovery section"""
        from PyQt5.QtCore import QPropertyAnimation, QEasingCurve, pyqtSignal
        from PyQt5.QtWidgets import QScrollBar
        
        scroll_bar = scroll_area.verticalScrollBar()
        
        self.discovery_scroll_animation = QPropertyAnimation(scroll_bar, b"value")
        self.discovery_scroll_animation.setDuration(180)  # Faster animation (reduced from 300ms)
        self.discovery_scroll_animation.setEasingCurve(QEasingCurve.OutQuart)  # Smoother easing
        
        original_wheel_event = scroll_area.wheelEvent
        
        def enhanced_smooth_wheel_event(event):
            angle_delta = event.angleDelta().y()
            steps = angle_delta / 120  # Standard wheel step
            current_value = scroll_bar.value()
            
            scroll_range = scroll_bar.maximum() - scroll_bar.minimum()
            if scroll_range > 300:
                scroll_amount = steps * 45  # Increased from 35 for faster scrolling
            else:
                scroll_amount = steps * 25  # Increased from 20 for faster scrolling
            
            if abs(steps) > 1:  # Multiple wheel steps
                scroll_amount *= 1.2  # 20% acceleration for fast scrolling
                
            target_value = current_value - scroll_amount
            
            target_value = max(scroll_bar.minimum(), min(scroll_bar.maximum(), target_value))
            
            if abs(target_value - current_value) > 0.1:  # Reduced threshold for more responsive
                self.discovery_scroll_animation.stop()
                self.discovery_scroll_animation.setStartValue(current_value)
                self.discovery_scroll_animation.setEndValue(target_value)
                self.discovery_scroll_animation.start()
            
            event.accept()
        
        scroll_area.wheelEvent = enhanced_smooth_wheel_event
    
    def ensure_discovery_scroll_works(self):
        """Ensure discovery scroll area can scroll to all content"""
        try:
            if hasattr(self, 'discovery_scroll_area'):
                self.discovery_scroll_area.widget().adjustSize()
                self.discovery_scroll_area.widget().updateGeometry()
                self.discovery_scroll_area.updateGeometry()
                
                from PyQt5.QtWidgets import QApplication
                QApplication.processEvents()
                
                scroll_bar = self.discovery_scroll_area.verticalScrollBar()
                content_widget = self.discovery_scroll_area.widget()
                
                content_height = content_widget.sizeHint().height()
                actual_content_height = content_widget.minimumSizeHint().height()
                viewport_height = self.discovery_scroll_area.viewport().height()
                
                final_content_height = max(content_height, actual_content_height)
                
                print(f"Discovery scroll - Content: {final_content_height}px, Viewport: {viewport_height}px")
                
                if final_content_height > viewport_height:
                    max_scroll = final_content_height - viewport_height
                    scroll_bar.setRange(0, max_scroll)
                    print(f"Scroll range set to: 0-{max_scroll}")
                else:
                    scroll_bar.setRange(0, 0)
                    print("No scrolling needed - content fits in viewport")
                
                if final_content_height > viewport_height:
                    self.discovery_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
                else:
                    self.discovery_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                
                scroll_bar.update()
                
        except Exception as e:
            print(f"Error updating discovery scroll: {e}")
    
    def scroll_discovery_to_bottom(self):
        """Scroll discovery area to bottom"""
        try:
            if hasattr(self, 'discovery_scroll_area'):
                self.discovery_scroll_area.widget().adjustSize()
                self.discovery_scroll_area.updateGeometry()
                
                from PyQt5.QtWidgets import QApplication
                QApplication.processEvents()
                
                scroll_bar = self.discovery_scroll_area.verticalScrollBar()
                max_value = scroll_bar.maximum()
                
                if max_value > 0:
                    scroll_bar.setValue(max_value)
                    print(f"Scrolled to bottom: {max_value}")
                else:
                    print("No scroll range available")
        except Exception as e:
            print(f"Error scrolling to bottom: {e}")
    
    def update_connected_devices(self):
        """Update the list of connected devices periodically with real-time status"""
        try:
            current_time = time.time()
            devices_to_remove = []
            
            for device_key, device_data in self.real_connected_devices.items():
                device_ip = device_data['ip']
                
                try:
                    time_since_connect = current_time - device_data['timestamp']
                    
                    if time_since_connect < 300:  # 5 minutes
                        is_connected = True
                    else:
                        is_connected = device_data.get('last_verified', 0) > (current_time - 60)  # Verified within last minute
                    
                except Exception as conn_error:
                    is_connected = False
                    self.log_message(f"Connection test failed for {device_data['name']}: {conn_error}")
                
                old_status = device_data['status']
                new_status = 'connected' if is_connected else 'disconnected'
                
                if old_status != new_status:
                    device_data['status'] = new_status
                    self.log_message(f"Device {device_data['name']} ({device_ip}) status: {old_status} → {new_status}")
                
                if not is_connected:
                    time_since_connect = current_time - device_data['timestamp']
                    if time_since_connect > 900:  # Remove after 15 minutes of no connection (increased from 10)
                        devices_to_remove.append(device_key)
            
            for device_key in devices_to_remove:
                if device_key in self.real_connected_devices:
                    device_info = self.real_connected_devices[device_key]
                    self.log_message(f"Removed inactive device: {device_info['name']} ({device_info['ip']})")
                    del self.real_connected_devices[device_key]
            
            if devices_to_remove or any(device_data.get('status_changed', False) for device_data in self.real_connected_devices.values()):
                self.refresh_connected_devices_display()
                    
        except KeyboardInterrupt:
            self.log_message("Connection monitoring interrupted by user")
            return
        except Exception as e:
            self.log_message(f"Error updating connected devices: {e}")
            import traceback
            traceback.print_exc()
    
    def add_connected_device(self, device_info, connection_method=""):
        """Add a device to the connected devices list"""
        try:
            device_name = device_info.get('name', 'Unknown Device')
            device_ip = device_info.get('ip', 'Unknown IP')
            
            device_key = f"{device_name}_{device_ip}"
            self.real_connected_devices[device_key] = {
                'name': device_name,
                'ip': device_ip,
                'method': connection_method,
                'timestamp': time.time(),
                'status': 'connected'
            }
            
            self.refresh_connected_devices_display()
            
            self.log_message(f"Added to connected devices: {device_name} ({device_ip}) via {connection_method}")
            
        except Exception as e:
            self.log_message(f"Error adding connected device: {e}")
    
    def pause_connected_devices_monitoring(self):
        """Pause connected devices monitoring to prevent blocking operations"""
        if hasattr(self, 'connected_devices_timer') and self.connected_devices_timer:
            if self.connected_devices_timer.isActive():
                self.connected_devices_timer.stop()
                self.log_message("Paused connected devices monitoring")
    
    def resume_connected_devices_monitoring(self):
        """Resume connected devices monitoring"""
        if hasattr(self, 'connected_devices_timer') and self.connected_devices_timer:
            if not self.connected_devices_timer.isActive():
                self.connected_devices_timer.start(10000)  # 10 second interval
                self.log_message("Resumed connected devices monitoring")
    
    def refresh_connected_devices_display(self):
        """Refresh the connected devices display based on real connections"""
        try:
            self.connected_devices_list.clear()
            
            if self.real_connected_devices:
                for device_key, device_data in self.real_connected_devices.items():
                    connection_icon = {
                        'link': '🔗',
                        'code': '🔢', 
                        'discovery': '📱',
                        'manual': '🔧'
                    }.get(device_data['method'], '📱')
                    
                    status_icon = '🟢' if device_data['status'] == 'connected' else '🟡'
                    device_name = device_data['name']
                    device_ip = device_data['ip']
                    
                    device_display = f"{status_icon} {connection_icon} {device_name} ({device_ip})"
                    
                    item = QListWidgetItem(device_display)
                    item.setData(Qt.UserRole, device_data)  # Store device data for later use
                    item.setToolTip(f"Status: {device_data['status'].upper()}\nConnected via: {device_data['method'].upper()}\nIP: {device_ip}\nDevice: {device_name}")
                    self.connected_devices_list.addItem(item)
            else:
                placeholder = QListWidgetItem("⏳ No devices connected yet - Connect via Code/Link or Discovery")
                placeholder.setFlags(placeholder.flags() & ~Qt.ItemIsSelectable)
                self.connected_devices_list.addItem(placeholder)
                
        except Exception as e:
            self.log_message(f"Error refreshing connected devices display: {e}")
    
    def get_selected_devices(self):
        """Get list of selected devices from the device list"""
        selected_devices = []
        selected_items = self.device_list.selectedItems()
        
        for item in selected_items:
            device_text = item.text()
            if '(' in device_text and ')' in device_text and "No devices found" not in device_text:
                try:
                    target_ip = device_text.split('(')[1].split(')')[0]
                    device_name = device_text.split('(')[0].strip()
                    
                    parts = target_ip.split('.')
                    if len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts):
                        selected_devices.append({
                            'ip': target_ip,
                            'name': device_name,
                            'display': device_text
                        })
                except Exception as e:
                    self.log_message(f"Error parsing device: {device_text} - {e}")
                    
        return selected_devices


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
