# compile using pyinstaller --windowed --onefile --icon=assets/petri-dish96.ico exPYre.py
import sqlite3
from datetime import datetime, timedelta
import os
from tkinter import Tk, filedialog, messagebox
import configparser
import sys
import threading
from notifypy import Notify
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog, QInputDialog, QHBoxLayout, QMessageBox, QComboBox
from PyQt5.QtGui import QIcon
import subprocess

SETTINGS_FILE = "database_settings.ini"
INTERVAL_SETTINGS = "interval_settings.ini"
TRAY_ICON = "assets/petri-dish96.ico"
databases_window = None  # Initializes databases_window globally
settings_window = None  # Initializes settings_window globally
notifications_paused = False # Global variable to track if notifications are paused
timer = None # initialise timer globally 

class DatabaseScanner:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

    def get_upcoming_events(self):
        today = datetime.now().date()
        two_weeks_later = today + timedelta(days=14)
        query = "SELECT * FROM products WHERE expiry_date >= ? AND expiry_date <= ?"
        self.cursor.execute(query, (today, two_weeks_later))
        return self.cursor.fetchall()

    def get_past_events(self):
        yesterday = datetime.now().date() - timedelta(days=1)
        query = "SELECT * FROM products WHERE expiry_date <= ?"
        self.cursor.execute(query, (yesterday,))
        return self.cursor.fetchall()

    def close(self):
        self.conn.close()

class DatabasesWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Databases")
        self.layout = QVBoxLayout(self)
        
        self.label = QLabel("Loaded Databases:")
        self.layout.addWidget(self.label)
        
        self.database_labels = []
        self.database_widgets = []
        self.remove_buttons = []
        self.add_button = None
        self.refresh_ui()
        
    def refresh_ui(self):
        # Clear existing database widgets, labels, remove buttons, and "Add Database" button
        for label in self.database_labels:
            label.setParent(None)
        for button in self.remove_buttons:
            button.setParent(None)
        for widget in self.database_widgets:
            widget.setParent(None)
        if self.add_button:
            self.add_button.setParent(None)
        
        # Clear the lists storing database widgets, labels and remove buttons
        self.database_labels.clear()
        self.remove_buttons.clear()
        self.database_widgets = []
        self.add_button = None
        
        # Get the current database settings
        database_settings = load_settings()
        
        # Display database widgets
        for name, path in database_settings.items():
            database_widget = QWidget()
            hbox = QHBoxLayout()
            label = QLabel(f"{name}: {path}")
            hbox.addWidget(label)
            remove_button = QPushButton("Remove")
            remove_button.clicked.connect(lambda _, n=name: self.remove_database(n))  # Pass name as an argument
            hbox.addWidget(remove_button)
            database_widget.setLayout(hbox)
            self.layout.addWidget(database_widget)
            self.database_widgets.append(database_widget)
            self.database_labels.append(label)  # Append label to database_labels list
            self.remove_buttons.append(remove_button)  # Append remove button to remove_buttons list

        # Set fixed width for remove buttons
        max_button_width = 100 
        for button in self.remove_buttons:
            button.setFixedWidth(max_button_width)

        # Add the "Add Database" button after displaying database widgets
        self.add_button = QPushButton("Add Database")
        self.add_button.clicked.connect(self.add_database)
        self.layout.addWidget(self.add_button)
        
    def add_database(self):
        # Prompt the user with a custom dialog box
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Add Database.")
        msg_box.setText("What would you like to do?")
        msg_box.addButton("Create New Database", QMessageBox.YesRole)
        msg_box.addButton("Load Existing Database", QMessageBox.NoRole)
        choice = msg_box.exec_()
    
        # Check the user's choice and handle accordingly
        if choice == 0:
            # User wants to create a new database
            file_path = create_new_db()    
        elif choice == 1:
            # User wants to load an existing database
            file_path = filedialog.askopenfilename(title="Select Database File", filetypes=[("Database Files", "*.db")])

        if file_path:
            # Prompt the user to enter a custom name for the database
            custom_name, _ = QInputDialog.getText(self, "Custom Name", "Enter a custom name for the database (optional):\n\n e.g 'PCR Lab Reagents'")
            if not custom_name:
                custom_name = os.path.basename(file_path)  # Use the database file name as the custom name
                
            # Update the settings file with the new database path and custom name
            database_settings = load_settings()
            database_settings[custom_name] = file_path
            save_settings(database_settings)
            
            # Refresh the UI to display the new database
            self.refresh_ui()

    def remove_database(self, name):
        reply = QMessageBox.question(self, 'Remove Database', f"Are you sure you want to remove '{name}'?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            # Remove the database from settings
            database_settings = load_settings()
            if name in database_settings:
                del database_settings[name]
                save_settings(database_settings)
            # Refresh the UI to update the displayed databases
            self.refresh_ui()

    def closeEvent(self, event):
        self.hide()
        event.ignore()  # Ignore the close event to keep the window hidden

class SettingsWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.layout = QVBoxLayout(self)
        
        self.label = QLabel("Database Scan Interval:")
        self.layout.addWidget(self.label)

        self.interval_combobox = QComboBox()
        self.interval_combobox.addItem("Every 15 minutes", 15 * 60)
        self.interval_combobox.addItem("Every 30 minutes", 30 * 60)
        self.interval_combobox.addItem("Every Hour", 60 * 60)
        self.interval_combobox.addItem("Every 2 Hours", 120 * 60)
        self.interval_combobox.addItem("Every 3 Hours", 180 * 60)
        self.interval_combobox.addItem("Every 4 Hours", 240 * 60)
        self.interval_combobox.addItem("Every 24 hours", 24 * 60 * 60)
        self.layout.addWidget(self.interval_combobox)

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_settings)
        self.layout.addWidget(self.save_button)

        self.load_current_interval()

    def save_settings(self):
        selected_interval = self.interval_combobox.currentData()
        save_interval({"scan_interval": selected_interval})

    def load_current_interval(self):
        settings = load_interval()
        if "scan_interval" in settings:
            interval = int(settings["scan_interval"])
            index = self.interval_combobox.findData(interval)
            if index != -1:
                self.interval_combobox.setCurrentIndex(index)

    def closeEvent(self, event):
        self.hide()
        event.ignore()  # Ignore the close event to keep the window hidden

def show_settings_window():
    global settings_window
    if settings_window is None:
        settings_window = SettingsWindow()
    settings_window.show()

def show_toast(title, message):
    notification = Notify()
    notification.title = title
    notification.message = message
    notification.icon = "assets/petri-dish96alert.ico"
    notification.send()

def get_database_path():
    # Prompt the user with a custom dialog box
    msg_box = QMessageBox()
    msg_box.setWindowTitle("No Database Selected")
    msg_box.setText("No database selected. What would you like to do?")
    msg_box.addButton("Create New Database", QMessageBox.YesRole)
    msg_box.addButton("Load Existing Database", QMessageBox.NoRole)
    choice = msg_box.exec_()
    
    # Check the user's choice and handle accordingly
    if choice == 0:
        # User wants to create a new database
        return create_new_db()    
    elif choice == 1:
        # User wants to load an existing database
        return filedialog.askopenfilename(title="Select Database File", filetypes=[("Database Files", "*.db")])

# Function to create a new database file
def create_new_db():
    file_path = filedialog.asksaveasfilename(defaultextension=".db", filetypes=[("Database files", "*.db")])
    if file_path:
        conn = sqlite3.connect(file_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS products
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT NOT NULL,
                      expiry_date DATE NOT NULL)''')
        conn.commit()
        conn.close()
        messagebox.showinfo("Info", f"New database created at the specified location.")
        return file_path

def save_settings(database_settings):
    existing_settings = load_settings()
    existing_settings.update(database_settings)  # Update with new settings
    config = configparser.ConfigParser()
    config['Settings'] = existing_settings
    with open(SETTINGS_FILE, 'w') as configfile:
        config.write(configfile)

def save_interval(scan_interval):
    config = configparser.ConfigParser()
    config['Settings'] = scan_interval
    with open(INTERVAL_SETTINGS, 'w') as configfile:
        config.write(configfile)

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        # If settings file doesn't exist, prompt the user to select a database file
        database_path = get_database_path()
        if database_path:
            # Prompt the user to enter a custom name for the database
            custom_name, _ = QInputDialog.getText(None, "Custom Name", "Enter a custom name for the database (optional):\n\n e.g 'PCR Lab Reagents'")
            if not custom_name:
                custom_name = os.path.basename(database_path)
            
            # Create a new settings file with the selected database path and custom name
            config = configparser.ConfigParser()
            config['Settings'] = {custom_name: database_path}
            with open(SETTINGS_FILE, 'w') as configfile:
                config.write(configfile)
            additional_databases_prompt()
            return dict(config['Settings'])
        else:
            QMessageBox.warning(None, "Warning", "No Database Selected. Exiting.", QMessageBox.Ok)
            exit_program()
    else:
        config = configparser.ConfigParser()
        config.read(SETTINGS_FILE)
        try:
            return dict(config['Settings'])
        except KeyError:
            QMessageBox.warning(None, "Warning", "Settings Read Error. Exiting.", QMessageBox.Ok)
            exit_program()

def load_interval():
    default_settings = {"scan_interval": 3 * 60 * 60}  # Default scan interval is 3 hours
    if not os.path.exists(INTERVAL_SETTINGS):
        save_interval(default_settings)
        return load_interval()
    else:
        config = configparser.ConfigParser()
        config.read(INTERVAL_SETTINGS)
        try:
            settings = dict(config['Settings'])
            if "scan_interval" not in settings:
                settings["scan_interval"] = default_settings["scan_interval"]
            return settings
        except KeyError:
            return default_settings
        
def additional_databases_prompt():
    # Ask user if they would like to monitor more databases
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Question)
    msg_box.setWindowTitle("Monitor More Databases")
    msg_box.setText("Would you like to monitor further databases?")
    msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    msg_box.setDefaultButton(QMessageBox.No)
    response = msg_box.exec_()

    if response == QMessageBox.Yes:
        # Prompt the user with a custom dialog box
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Add Database.")
        msg_box.setText("What would you like to do?")
        msg_box.addButton("Create New Database", QMessageBox.YesRole)
        msg_box.addButton("Load Existing Database", QMessageBox.NoRole)
        choice = msg_box.exec_()
    
        # Check the user's choice and handle accordingly
        if choice == 0:
            # User wants to create a new database
            file_path = create_new_db()    
        elif choice == 1:
            # User wants to load an existing database
            file_path = filedialog.askopenfilename(title="Select Database File", filetypes=[("Database Files", "*.db")])

        if file_path:
            # Prompt the user to enter a custom name for the database
            custom_name, _ = QInputDialog.getText(None, "Custom Name", "Enter a custom name for the database (optional):\n\n e.g 'PCR Lab Reagents'")
            if not custom_name:
                custom_name = os.path.basename(file_path)  # Use the database file name as the custom name
                
            # Update the settings file with the new database path and custom name
            database_settings = load_settings()
            database_settings[custom_name] = file_path
            save_settings(database_settings)
        additional_databases_prompt()
    else:
        return
        
def open_databases_window():
    global databases_window
    if databases_window is None:
        databases_window = DatabasesWindow()
    databases_window.show()

def pause_notifications_24h():
    global notifications_paused
    notifications_paused = True

    # Start a timer to resume notifications after 24 hours
    pause = threading.Timer(24 * 60 * 60, resume_notifications)
    pause.start()

def resume_notifications():
    global notifications_paused
    notifications_paused = False

def trigger_database_scan():
    # Load database paths from settings
    database_settings = load_settings()
    
    # Initialize the database scanner for each database
    for db_name, db_path in database_settings.items():
        db_path = str(db_path)  # Ensure db_path is a string
        scanner = DatabaseScanner(db_path)

        # Get upcoming events and show toast notifications if notifications are not paused
        if not notifications_paused:
            upcoming_events = scanner.get_upcoming_events()
            for event in upcoming_events:
                expiry_date = datetime.strptime(event[2], "%Y-%m-%d")
                days_until_expiry = (expiry_date - datetime.now()).days
                title = f"Upcoming Expiry - {db_name}"
                message = f"{event[1]} is expiring in {days_until_expiry + 1} days."
                show_toast(title, message)

                # update tray icon and tooltip
                if tray_icon.icon().name() != "assets/petri-dish96expired.ico":
                    tray_icon.setIcon(QIcon("assets/petri-dish96warn.ico"))
                    tray_icon.setToolTip("exPYre - an item is nearing expiry")

        # Get past events and show toast notifications if notifications are not paused
        if not notifications_paused:
            past_events = scanner.get_past_events()
            for event in past_events:
                title = f"Expiry - {db_name}"
                message = f"{event[1]} has now expired"
                show_toast(title, message)

                # update tray icon and tooltip
                tray_icon.setIcon(QIcon("assets/petri-dish96expired.ico"))
                tray_icon.setToolTip("exPYre - an item has expired")

        # Close the database connection
        scanner.close()

# Define a function to start a timer for the specified time interval
def start_timer(interval):
    global timer
    # Call perform_database_scan function immediately
    trigger_database_scan()
    # Schedule the perform_database_scan function to run periodically at the specified interval
    timer = threading.Timer(interval, start_timer, args=[interval])
    timer.start()

def tray_icon_double_clicked(reason):
    if reason == QSystemTrayIcon.DoubleClick:
        subprocess.Popen(['database_gui.exe'])

def exit_program():
    # Cancel the timer if it's running
    global timer
    if timer:
        timer.cancel()

    # Exit the program
    sys.exit()

def main():
    # initialise database paths in settings
    load_settings()

    # Ensure interval settings are loaded
    interval_settings = load_interval()

    # Extract the scan interval value from interval_settings
    scan_interval = int(interval_settings["scan_interval"])  # Default to 3 hours if not found

    # Start interval timer with the scan interval
    start_timer(scan_interval)

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Create a system tray icon
    tray_icon = QSystemTrayIcon()
    tray_icon.setIcon(QIcon(TRAY_ICON))
    tray_icon.setToolTip("exPYre")

    # Create a context menu for the system tray icon
    tray_menu = QMenu()
    scan_action = QAction("Scan Databases Now...", parent=app)
    scan_action.triggered.connect(trigger_database_scan)
    tray_menu.addAction(scan_action)
    pause_notifications_action = QAction("Pause Notifications for 24 Hours", parent=app)
    pause_notifications_action.triggered.connect(pause_notifications_24h)
    tray_menu.addAction(pause_notifications_action)
    databases_action = QAction("Manage Databases", parent=app)
    databases_action.triggered.connect(open_databases_window)
    tray_menu.addAction(databases_action)
    settings_action = QAction("Settings", parent=app)
    settings_action.triggered.connect(show_settings_window)
    tray_menu.addAction(settings_action)
    exit_action = QAction("Exit", parent=app)
    exit_action.triggered.connect(exit_program)
    tray_menu.addAction(exit_action)

    # Connect the activated signal to the tray_icon_double_clicked function
    tray_icon.activated.connect(tray_icon_double_clicked)

    # Set the tray menu for the system tray icon
    tray_icon.setContextMenu(tray_menu)
    tray_icon.show()

    # Run the main function
    main()

    app.exec_()
