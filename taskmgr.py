import sys
import psutil
import platform
import subprocess
import GPUtil
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QTabWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QMessageBox, QProgressBar,
    QLabel, QHBoxLayout
)
from PyQt6.QtGui import QColor, QFont, QPixmap, QKeySequence, QShortcut
from typing import Dict, List, Union
import glob

class SystemMonitor(QThread):
    data_updated = pyqtSignal(dict)

    def run(self):
        while True:
            try:
                data = {
                    'cpu': self._get_cpu_data(),
                    'gpu': self._get_gpu_data(),
                    'memory': self._get_memory_data(),
                    'disk': self._get_disk_data(),
                    'processes': self._get_process_data(),
                    'network': self._get_network_data()
                }
                self.data_updated.emit(data)
                self.msleep(3500)
            except Exception as e:
                print(f"Monitoring error: {e}")

    def _get_cpu_data(self) -> Dict[str, Union[str, float]]:
        freq = psutil.cpu_freq()
        return {
            "Model": self._get_cpu_model(),
            "Cores": f"{psutil.cpu_count(logical=False)}/{psutil.cpu_count(logical=True)}",
            "Frequency": f"{freq.current/1000:.1f} GHz" if freq else "N/A",
            "Temperature": self._get_cpu_temp(),
            "Load": psutil.cpu_percent()
        }

    def _get_cpu_model(self) -> str:
        try:
            if platform.system() == "Linux":
                for f in glob.glob("/proc/cpuinfo"):
                    with open(f, 'r') as cpuinfo:
                        for line in cpuinfo:
                            if line.strip().startswith('model name'):
                                return line.split(':')[1].strip().replace('(R)', '').replace('(TM)', '')
            return platform.processor()
        except Exception:
            return "Unknown"

    def _get_cpu_temp(self) -> str:
        try:
            if platform.system() == "Linux":
                for f in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
                    with open(f) as tfile:
                        return f"{int(tfile.read().strip())/1000:.1f}°C"
        except:
            return "N/A"

    def _get_gpu_data(self) -> List[Dict]:
        return [{
            'name': gpu.name,
            'memory': f"{gpu.memoryUsed:.1f}/{gpu.memoryTotal:.0f} GB",
            'load': gpu.load*100,
            'temp': gpu.temperature
        } for gpu in GPUtil.getGPUs()]

    def _get_memory_data(self) -> Dict:
        mem = psutil.virtual_memory()
        return {'total': mem.total, 'used': mem.used, 'percent': mem.percent}

    def _get_disk_data(self) -> List[Dict]:
        return [{
            'device': part.device.split('/')[-1],
            'mount': part.mountpoint,
            'total': (du := psutil.disk_usage(part.mountpoint)).total,
            'used': du.used,
            'percent': du.percent
        } for part in psutil.disk_partitions() if part.mountpoint]

    def _get_process_data(self):
        return sorted([
            (p.info['pid'], p.info['name'], p.info['cpu_percent'], p.info['memory_info'].rss)
            for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info'])
            if p.info['name']
        ], key=lambda x: x[2], reverse=True)[:100]

    def _get_network_data(self) -> Dict:
        net = psutil.net_io_counters()
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        return {
            'interfaces': {
                iface: {
                    'addresses': [addr.address for addr in addrs[iface]],
                    'stats': {
                        'bytes_sent': net.bytes_sent,
                        'bytes_recv': net.bytes_recv,
                        'is_up': stats[iface].isup if iface in stats else False
                    }
                } for iface in addrs
            }
        }

class SystemDashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.pinned_pid = None
        self.setWindowTitle("System Monitor Pro")
        self.setFixedSize(750, 600)  # Увеличил размер для новой вкладки
        self.init_ui()
        self.init_styles()
        self.start_monitoring()
        self._setup_shortcuts()

    def init_ui(self):
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_cpu_tab(), "CPU")
        self.tabs.addTab(self._create_gpu_tab(), "GPU")
        self.tabs.addTab(self._create_memory_tab(), "Memory")
        self.tabs.addTab(self._create_disk_tab(), "Storage")
        self.tabs.addTab(self._create_process_tab(), "Processes")
        self.tabs.addTab(self._create_network_tab(), "Network")  # Новая вкладка
        self.tabs.addTab(self._create_help_tab(), "Help")

        tab_layout = QHBoxLayout()
        tab_layout.addWidget(self.tabs)

        layout = QVBoxLayout()
        layout.addLayout(tab_layout)
        self.setLayout(layout)

    def _setup_shortcuts(self):
        self.shortcut_kill_pinned = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.shortcut_kill_pinned.activated.connect(self._kill_pinned_process)

    def _kill_pinned_process(self):
        if self.pinned_pid:
            confirm = QMessageBox.question(
                self, "Confirm Termination",
                f"Terminate process PID {self.pinned_pid}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if confirm == QMessageBox.StandardButton.Yes:
                try:
                    psutil.Process(self.pinned_pid).terminate()
                    self.pinned_pid = None
                    self._highlight_pinned_process()
                    QMessageBox.information(self, "Success", "Pinned process terminated")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Error: {str(e)}")
        else:
            QMessageBox.warning(self, "Warning", "No pinned process selected")

    def _create_help_tab(self):
        help_text = """
        <h2 style="color:#4CAF50; margin-bottom:15px;">System Monitor Pro v2.1</h2>
        <p style="font-size:14px; color:#eee;">Author: <b>mihatskiyi</b></p>
        <p style="margin-top:20px;">Core Features:</p>
        <ul style="font-size:13px; color:#ccc;">
            <li>Real-time CPU monitoring</li>
            <li>GPU performance metrics</li>
            <li>Memory & disk utilization analysis</li>
            <li>Process management</li>
            <li>Network statistics</li>
        </ul>
        <p style="margin-top:20px;">Hotkeys:</p>
        <ul style="font-size:13px; color:#ccc;">
            <li>Ctrl+Z: Terminate pinned process</li>
        </ul>
        <p style="margin-top:20px; color:#666;">© 2025 All rights reserved</p>
        """
        label = QLabel(help_text)
        label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        label.setContentsMargins(20, 20, 20, 20)
        return label
    
    def _create_table(self, headers: List[str]) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setAlternatingRowColors(True)
        return table

    def _create_cpu_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        self.cpu_meter = QProgressBar()
        self.cpu_meter.setFormat("CPU load: %p%")
        self.cpu_meter.setMaximumHeight(30)
        
        self.cpu_table = self._create_table(["Option", "Value"])
        
        layout.addWidget(self.cpu_meter)
        layout.addWidget(self.cpu_table)
        widget.setLayout(layout)
        return widget

    def _create_gpu_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        self.gpu_meter = QProgressBar()
        self.gpu_meter.setFormat("GPU load: %p%")
        self.gpu_meter.setMaximumHeight(30)
        
        self.gpu_table = self._create_table(["Device", "Memory", "Load", "Temperature"])
        
        layout.addWidget(self.gpu_meter)
        layout.addWidget(self.gpu_table)
        widget.setLayout(layout)
        return widget

    def _create_memory_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        self.mem_meter = QProgressBar()
        self.mem_meter.setFormat("Memory utilization: %p%")
        self.mem_meter.setMaximumHeight(30)
        
        self.mem_table = self._create_table(["Total", "Used", "Available"])
        
        layout.addWidget(self.mem_meter)
        layout.addWidget(self.mem_table)
        widget.setLayout(layout)
        return widget

    def _create_disk_tab(self):
        self.disk_table = self._create_table(["Device", "Mount point.", "Total", "Used", "Free", "Usage"])
        return self.disk_table

    def _create_process_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        self.process_table = self._create_table(["PID", "Name", "CPU %", "Memory"])
        self.process_table.cellClicked.connect(self._toggle_pinned_process)
        
        self.kill_btn = QPushButton("Terminate the process")
        self.kill_btn.clicked.connect(self._kill_process)
        
        layout.addWidget(self.process_table)
        layout.addWidget(self.kill_btn)
        widget.setLayout(layout)
        return widget

    def _create_network_tab(self):
        self.network_table = self._create_table(["Interface", "IP Addresses", "Status", "Sent", "Received"])
        return self.network_table

    def init_styles(self):
        self.setStyleSheet("""
            QWidget {
                background-color: rgb(32, 32, 32);
                color: #e0e0e0;
                font-family: 'Segoe UI';
                font-size: 12px;
            }
            QProgressBar {
                background: rgb(26, 26, 26);
                border: 1px solid rgb(42, 42, 42);
                border-radius: 4px;
                text-align: center;
                margin: 5px;
            }
            QProgressBar::chunk {
                background: #388E3C;
                border-radius: 4px;
            }
            QTableWidget {
                background: rgb(24, 24, 24);
                alternate-background-color: rgb(32, 32, 32);
                border: none;
                font-size: 11px;
            }
            QHeaderView::section {
                background: rgb(38, 38, 38);
                padding: 8px;
                border: none;
                color: #bdbdbd;
            }
            QTabBar::tab {
                background: rgb(38, 38, 38);
                color: #9e9e9e;
                padding: 8px 15px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: rgb(48, 48, 48);
                color: #388E3C;
            }
            QPushButton {
                background: #2E7D32;
                color: #ffffff;
                padding: 8px;
                border-radius: 4px;
                min-width: 100px;
                border: 1px solid #1B5E20;
            }
            QPushButton:hover {
                background: #388E3C;
            }
            QTableWidget QTableWidgetItem {
                color: #e0e0e0;
            }
        """)

    def start_monitoring(self):
        self.monitor = SystemMonitor()
        self.monitor.data_updated.connect(self._update_ui)
        self.monitor.start()

    def _update_ui(self, data):
        self._update_cpu(data['cpu'])
        self._update_gpu(data['gpu'])
        self._update_memory(data['memory'])
        self._update_disk(data['disk'])
        self._update_processes(data['processes'])
        self._update_network(data['network'])

    def _update_table(self, table: QTableWidget, data: List[List]):
        table.setRowCount(len(data))
        for row, items in enumerate(data):
            for col, item in enumerate(items):
                table.setItem(row, col, QTableWidgetItem(str(item)))

    def _update_cpu(self, data):
        self.cpu_meter.setValue(int(data['Load']))
        self._update_table(self.cpu_table, [
            ["Model", data['Model']],
            ["Cores/Threads", data['Cores']],
            ["Frequency", data['Frequency']],
            ["Temperature", data['Temperature']]
        ])

    def _update_gpu(self, data):
        if data:
            self.gpu_meter.setValue(int(data[0]['load']))
            gpu_info = [[
                g['name'],
                g['memory'],
                f"{g['load']:.0f}%",
                f"{g['temp']}°C"
            ] for g in data]
            self._update_table(self.gpu_table, gpu_info)
        else:
            self.gpu_meter.setValue(0)
            self._update_table(self.gpu_table, [["No GPU detected", "", "", ""]])

    def _update_memory(self, data):
        self.mem_meter.setValue(int(data['percent']))
        self._update_table(self.mem_table, [[
            f"{data['total']/(1024**3):.1f} GB",
            f"{data['used']/(1024**3):.1f} GB",
            f"{(data['total']-data['used'])/(1024**3):.1f} GB"
        ]])

    def _update_disk(self, data):
        disk_info = [[
            d['device'],
            d['mount'],
            f"{d['total']/(1024**3):.1f}G",
            f"{d['used']/(1024**3):.1f}G",
            f"{(d['total']-d['used'])/(1024**3):.1f}G",
            f"{d['percent']}%"
        ] for d in data]
        self._update_table(self.disk_table, disk_info)

    def _update_processes(self, processes):
        if self.pinned_pid:
            try:
                p = psutil.Process(self.pinned_pid)
                pinned_proc = (p.pid, p.name(), p.cpu_percent(), p.memory_info().rss)
                processes = [pinned_proc] + [proc for proc in processes if proc[0] != self.pinned_pid]
            except:
                self.pinned_pid = None

        display = [[
            p[0],
            p[1],
            f"{p[2]:.1f}%",
            f"{p[3]/1024**2:.1f} MB"
        ] for p in processes[:100]]

        self._update_table(self.process_table, display)
        self._highlight_pinned_process()

    def _update_network(self, data):
        network_info = []
        for iface, info in data['interfaces'].items():
            status = "Up" if info['stats']['is_up'] else "Down"
            network_info.append([
                iface,
                ", ".join(info['addresses']),
                status,
                f"{info['stats']['bytes_sent']/1024**2:.1f} MB",
                f"{info['stats']['bytes_recv']/1024**2:.1f} MB"
            ])
        self._update_table(self.network_table, network_info)

    def _highlight_pinned_process(self):
        highlight_color = QColor('#404040')
        default_color = QColor('#121212')
        
        for row in range(self.process_table.rowCount()):
            item = self.process_table.item(row, 0)
            if item and self.pinned_pid and int(item.text()) == self.pinned_pid:
                for col in range(self.process_table.columnCount()):
                    self.process_table.item(row, col).setBackground(highlight_color)
            else:
                for col in range(self.process_table.columnCount()):
                    self.process_table.item(row, col).setBackground(default_color)

    def _toggle_pinned_process(self, row, _):
        pid = int(self.process_table.item(row, 0).text())
        self.pinned_pid = pid if self.pinned_pid != pid else None
        self._highlight_pinned_process()

    def _kill_process(self):
        if (row := self.process_table.currentRow()) >= 0:
            try:
                pid = int(self.process_table.item(row, 0).text())
                psutil.Process(pid).terminate()
                QMessageBox.information(self, "Успешно", f"Процесс {pid} завершен")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка: {str(e)}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 9))
    window = SystemDashboard()
    window.show()
    sys.exit(app.exec())