# compile using pyinstaller --windowed --onefile --icon=assets/petri-dish96.ico --add-data "assets/*.ico;assets/" --hidden-import babel.numbers exPYre.py
import sqlite3
from datetime import datetime, timedelta
import os
from tkinter import Tk, ttk, filedialog, messagebox, Listbox
import configparser
import sys
import threading
from windows_toasts import Toast, ToastDisplayImage, WindowsToaster
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog, QInputDialog, QHBoxLayout, QMessageBox, QComboBox
from PyQt5.QtGui import QIcon
import subprocess
import customtkinter as ctk
from tkcalendar import Calendar
import webbrowser

# Directory converter for compiler
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# Icons
main_icon = resource_path("assets\\petri-dish96.ico")
alert_icon = resource_path("assets\\petri-dish96alert.ico")
expired_icon = resource_path("assets\\petri-dish96expired.ico")
warn_icon = resource_path("assets\\petri-dish96warn.ico")

# Configuration files
SETTINGS_FILE = resource_path("database_settings.ini")
INTERVAL_SETTINGS = resource_path("interval_settings.ini")
TRAY_ICON = main_icon

# Global variables
databases_window = None  # Initializes databases_window globally
settings_window = False  # Initializes settings_window globally
editor_window = False  # Initializes editor_window globally
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

class SettingsWindow(ctk.CTk):
    def __init__(self, parent=None):
        super().__init__()
        global databases
        global interval_set

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        # Create the main window
        self.wm_iconbitmap(main_icon)
        self.geometry("400x400")
        self.resizable(width=False, height=False)
        self.title("exPYre - Settings")

        # Create a CTkTabview for managing tabs
        tab_view = ctk.CTkTabview(master=self)
        tab_view.pack(pady=10, expand=True, fill="both")

        # Create tabs
        tab_view.add("Database Settings")
        tab_view.add("Notification Settings")
        tab_view.add("About exPYre")

        # Create layout for Database Settings Tab
        # Add/load buttons
        button_frame = ctk.CTkFrame(master=tab_view.tab("Database Settings"))
        button_frame.pack(pady=5, fill="x")
        addbutton = ctk.CTkButton(master=button_frame, text="Create New Database", command=self.create_database)
        addbutton.pack(side="left")
        loadbutton = ctk.CTkButton(master=button_frame, text="Load Database", command=self.load_database)
        loadbutton.pack(side="right")
        # Database list and delete button
        databasetitlelabel = ctk.CTkLabel(master=tab_view.tab("Database Settings"), text="Loaded Databases:")
        databasetitlelabel.pack()
        databases = Listbox(master=tab_view.tab("Database Settings"), selectmode= "single", height=5)
        databases.pack(fill="x", pady=5)
        scrollbar = ctk.CTkScrollbar(databases)
        scrollbar.configure(command=databases.yview)
        scrollbar.pack(side="right", fill="y")
        databases.config(yscrollcommand=scrollbar.set)
        self.refresh_databases()
        removebutton = ctk.CTkButton(master=tab_view.tab("Database Settings"), text="Remove Selected Database", command=lambda: self.remove_database(databases.get(databases.curselection()[0])))
        removebutton.pack(pady=5, anchor="s")
        
        # Create layout for Notification Settings Tab
        interval_label = ctk.CTkLabel(master=tab_view.tab("Notification Settings"), text="Notify me every...") 
        interval_label.pack(pady=5)
        interval_set = ctk.CTkComboBox(master=tab_view.tab("Notification Settings"), values=["15 minutes", "30 minutes", "1 hour", "2 hours", "3 hours", "4 hours", "24 hours"],
                                     command=self.save_settings)
        interval_set.set(self.interval_translator(int(self.load_current_interval())))
        interval_set.pack()

        # Create layout for About tab
        text_box = ctk.CTkLabel(master=tab_view.tab("About exPYre"), text="exPYre was written by Ian Nicholls in Python 3.11 \nand is distributed under MIT licence.")
        text_box.pack(pady=20)
        github_button = ctk.CTkButton(master=tab_view.tab("About exPYre"), text="GitHub",command= lambda: webbrowser.open("https://github.com/Ian-Nicholls89/exPYre"))
        github_button.pack()

        # Catch when window is closed and allow it to be reopened again later
        self.protocol("WM_DELETE_WINDOW", self.closeEvent)

    def interval_translator(self, choice):
        if choice == 15*60:
            choice = "15 minutes"
        elif choice == 30*60:
            choice = "30 minutes"
        elif choice == 60*60:
            choice = "1 hour"
        elif choice == 120*60:
            choice = "2 hours"
        elif choice == 180*60:
            choice = "3 hours"
        elif choice == 240*60:
            choice = "4 hours"
        elif choice == 24*60*60:
            choice = "24 hours"
        
        return choice

    def save_settings(self, choice):
        if choice == "15 minutes":
            choice = 15*60
        elif choice == "30 minutes":
            choice = 30*60
        elif choice == "1 hour":
            choice = 60*60
        elif choice == "2 hours":
            choice = 120*60
        elif choice == "3 hours":
            choice = 180*60
        elif choice == "4 hours":
            choice = 240*60
        elif choice == "24 hours":
            choice = 24*60*60
        else:
            choice = 180*60
        save_interval({"scan_interval": choice})
    
    def load_current_interval(self):
        settings = load_interval()
        if "scan_interval" in settings:
            interval = int(settings["scan_interval"])
            return interval
        
    def refresh_databases(self):
        # Clear existing items in the listbox
        for item in databases.get(0, 'end'):
            databases.delete(item)

        # Add databases back to the listbox
        database_list = load_settings()
        for entry in database_list:
            databases.insert("end", entry)

    def create_database(self):
        # Create new db
        file_path = create_new_db()

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
            self.refresh_databases()
        
    def load_database(self):
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
            self.refresh_databases()

    def remove_database(self, name):
            reply = messagebox.askyesno("Confirmation", f"Are you sure you want to delete \"{name}\" database?")
            if reply:
                try:
                    # Remove the database from settings
                    database_settings = load_settings()
                    if name in database_settings:
                        del database_settings[name]
                        save_settings(database_settings)
                    # Refresh the UI to update the displayed databases
                    self.refresh_databases()
                except ValueError:
                    messagebox.showerror("Error", "Database not found.")
    
    def closeEvent(self):
        global settings_window
        settings_window = False
        self.destroy()

class DatabaseEditor(ctk.CTk):
    def __init__(self, parent=None):
        super().__init__()
        global treeview
        global product_name_entry
        global calendar
        global database_settings
        # Load all databases from settings file
        database_settings = load_settings()

        # Load first database into editing mode
        for name, info in database_settings.items():
            self.switch_database(name, info)
            break

        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        # Create the main window
        self.wm_iconbitmap(main_icon)
        self.geometry("600x400")
        self.title("exPYre - Database Editor")

        # Create a dropdown menu
        self.database_dropdown()
        dropdown = ctk.CTkOptionMenu(self, values=list(db_names), command=self.change_database_dropdown)
        dropdown.pack(padx=10, pady=10)

        # Create a CTkTabview for managing tabs
        tab_view = ctk.CTkTabview(master=self)
        tab_view.pack(pady=10, expand=True, fill="both")

        # Create tabs
        tab_view.add("Show All Items")
        tab_view.add("Add Products")

        # Create a treeview for displaying products in tab1
        treeview = ttk.Treeview(master=tab_view.tab("Show All Items"), columns=("Product", "Expiry Date"))
        treeview.pack(expand=True, fill="both")
        treeview.column("#0", width=0)
        treeview.heading("Product", text="Product")
        treeview.heading("Expiry Date", text="Expiry Date")
        

        # Populate the treeview with sample data
        self.populate_treeview(self.fetch_data())

        # Create the delete button
        delete_button = ctk.CTkButton(master=tab_view.tab("Show All Items"), text="Delete Selected", command=self.delete_item)
        delete_button.pack(pady=10)

        # Create entry fields and button for adding products in tab2
        product_name_entry = ctk.CTkEntry(master=tab_view.tab("Add Products"), placeholder_text="Product Name")
        product_name_entry.pack(pady=1)

        # Expiry date label and calendar
        expiry_label = ctk.CTkLabel(master=tab_view.tab("Add Products"), text="Expiry Date:")
        expiry_label.pack(pady=1)
        calendar = Calendar(master=tab_view.tab("Add Products"), selectmode='day')
        calendar.pack(pady=5)

        # Submit button
        add_button = ctk.CTkButton(master=tab_view.tab("Add Products"), text="Add Product", command=self.add_product)
        add_button.pack()

        # Catch when window is closed and allow it to be reopened again later
        self.protocol("WM_DELETE_WINDOW", self.closeEvent)

    # Function to load the database files from the settings file created in main program
    def load_settings(self):
        global editor_window
        if not os.path.exists(SETTINGS_FILE):
            # If settings file doesn't exist, produce warning and close editor
            messagebox.showwarning("Warning", "No database selected. Please select a database in exPYre settings.")
            editor_window = False
            self.destroy()
        else:
            config = configparser.ConfigParser()
            config.read(SETTINGS_FILE)
            try:
                return dict(config['Settings'])
            except KeyError:
                messagebox.showwarning("Warning", "Settings read error. Exiting editor.")
                editor_window = False
                self.destroy()

    def fetch_data(self):
        # fetch all data
        global items
        conn = sqlite3.connect(db_location)
        c = conn.cursor()
        c.execute("SELECT * FROM products")
        items = c.fetchall()
        conn.close()

        return items

    def populate_treeview(self, products):
        # Clear existing items in the treeview
        for item in treeview.get_children():
            treeview.delete(item)

        # Add new products to the treeview
        for id, product, expiry_date in products:
            treeview.insert("", "end", values=(product, expiry_date))

    def database_dropdown(self):
        global db_names
        db_names = []
        for name, info in database_settings.items():
            db_names.append(name)

    def change_database_dropdown(self, name):
        global db_location
        if name in database_settings:
            db_location = database_settings[name]
            self.populate_treeview(self.fetch_data())

    # Function to delete selected item
    def delete_item(self):
        selected_item_id = treeview.focus()
        if selected_item_id:
            confirm = messagebox.askyesno("Confirmation", "Are you sure you want to delete this item?")
            if confirm:
                try:
                    # Convert string ID to integer index (assuming IDs are unique)
                    selected_item_index = treeview.get_children().index(selected_item_id)
                    selected_item_data = items[selected_item_index]  # Access data using the integer index
                    selected_item_id = selected_item_data[0]  # Extract ID from the data list
                    conn = sqlite3.connect(db_location)
                    c = conn.cursor()
                    c.execute("DELETE FROM products WHERE id=?", (selected_item_id,))
                    conn.commit()
                    conn.close()
                    self.populate_treeview(self.fetch_data())
                except ValueError:
                    messagebox.showerror("Error", "Item not found in treeview.")

    def add_product(self):
        global calendar
        global items    
        # Get the product name from the entry widget
        product_name = product_name_entry.get().strip() if product_name_entry else ''  # Strip whitespace from the input if product_entry is not None

        # Check if the product name is empty
        if not product_name:
            messagebox.showinfo("Info", "Please enter a product name.")
            product_name_entry.focus_set()  # Set focus to the product name entry widget
            return

        # Get the expiry date from the calendar widget
        expiry_date = calendar.selection_get().strftime('%Y-%m-%d')

        # Connect to the database and add the product
        conn = sqlite3.connect(db_location)
        c = conn.cursor()
        c.execute("INSERT INTO products (name, expiry_date) VALUES (?, ?)", (product_name, expiry_date))
        conn.commit()
        conn.close()

        # Clear the product entry widget
        if product_name_entry:
            product_name_entry.delete(0, ctk.END)
            product_name_entry.focus_set()
        
        # Update the dataset in the database
        self.populate_treeview(self.fetch_data())
        

    # Function to switch to a selected database
    def switch_database(self, name, info):
        global db_location
        db_location = info

    def closeEvent(self):
        global editor_window
        editor_window = False
        self.destroy()

def show_editor_window():
    global editor_window
    if editor_window is False:
        editor_window = True
        editor = DatabaseEditor()
        editor.mainloop()

def show_settings_window():
    global settings_window
    if settings_window is False:
        settings_window = True
        settings = SettingsWindow()
        settings.mainloop()

def show_toast(title, message):
    toaster = WindowsToaster('exPYre')
    newToast = Toast()
    newToast.text_fields = [f"{title}", f"{message}"]
    newToast.AddImage(ToastDisplayImage.fromPath(alert_icon))
    newToast.on_activated = lambda _: show_editor_window()
    toaster.show_toast(newToast)

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
    default_settings = {"scan_interval": 180*60}  # Default scan interval is 3 hours
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
                title = f"Upcoming Expiry in \"{db_name}\""
                message = f"\"{event[1]}\" is expiring in {days_until_expiry + 1} days."
                show_toast(title, message)

                # update tray icon and tooltip
                if tray_icon.icon().name() != expired_icon:
                    tray_icon.setIcon(QIcon(warn_icon))
                    tray_icon.setToolTip("exPYre - an item is nearing expiry")

        # Get past events and show toast notifications if notifications are not paused
        if not notifications_paused:
            past_events = scanner.get_past_events()
            for event in past_events:
                title = f"Expiry in \"{db_name}\""
                message = f"\"{event[1]}\" has now expired"
                show_toast(title, message)

                # update tray icon and tooltip
                tray_icon.setIcon(QIcon(expired_icon))
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
        show_editor_window()

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
    database_editor = QAction("Database Editor", parent=app)
    database_editor.triggered.connect(show_editor_window)
    tray_menu.addAction(database_editor)
    pause_notifications_action = QAction("Pause Notifications for 24 Hours", parent=app)
    pause_notifications_action.triggered.connect(pause_notifications_24h)
    tray_menu.addAction(pause_notifications_action)
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
