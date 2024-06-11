# compile using pyinstaller --windowed --onefile --icon=assets/petri-dish96.ico --add-data "assets/*.ico;assets/" --hidden-import babel.numbers --hidden-import winrt.windows.foundation.collections IMPP.py
import sqlite3
from datetime import datetime, timedelta
import os
from tkinter import Tk, ttk, filedialog, messagebox, PhotoImage, simpledialog
import configparser
import sys
import threading
from windows_toasts import Toast, ToastDisplayImage, WindowsToaster
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog, QInputDialog, QHBoxLayout, QMessageBox, QComboBox
from PyQt5.QtGui import QIcon
import customtkinter as ctk
from tkcalendar import Calendar
import webbrowser
from win32com.client import Dispatch
import winshell
from PIL import Image
import screeninfo

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
main_icon = resource_path("assets\\IMPP\\IMPPcuteimp.png")
toast_alert_icon = resource_path("assets\\IMPP\\IMPPcuteimpwarn.png")
toast_expired_icon = resource_path("assets\\IMPP\\IMPPcuteimpexp.png")
expired_icon = resource_path("assets\\IMPP\\IMPPcuteimpexptray.png")
warn_icon = resource_path("assets\\IMPP\\IMPPcuteimpwarntray.png")
app_logo = resource_path("assets\\IMPP\\IMPPcute.png")

# Configuration files
SETTINGS = "settings.ini"
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
        days_setting = int(load_settings("Notifications", "notify_days"))
        later = today + timedelta(days=days_setting)
        query = "SELECT * FROM products WHERE expiry_date >= ? AND expiry_date <= ?"
        self.cursor.execute(query, (today, later))
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
        self.title("IMPP - Settings")

        # Create a CTkTabview for managing tabs
        tab_view = ctk.CTkTabview(master=self)
        tab_view.pack(pady=10, expand=True, fill="both")

        # Create tabs
        tab_view.add("Database Settings")
        tab_view.add("Notification Settings")
        tab_view.add("About IMPP")

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

        databases = ttk.Treeview(master=tab_view.tab("Database Settings"), columns=("Name", "Location"), show="headings")
        # Set the display names for the columns
        databases.heading("Name", text="Name")
        databases.heading("Location", text="Location")
        databases.pack(fill="x", pady=5) #(expand=True, fill="both")

        scrollbar = ctk.CTkScrollbar(databases)
        scrollbar.configure(command=databases.yview)
        scrollbar.pack(side="right", fill="y")
        databases.configure(yscrollcommand=scrollbar.set)

        self.refresh_databases()
        
        removebutton = ctk.CTkButton(master=tab_view.tab("Database Settings"), text="Remove Selected Database", command=lambda: self.remove_database(databases.item(databases.focus())["values"]))
        removebutton.pack(pady=5, anchor="s")  

        # Create layout for Notification Settings Tab
        interval_label = ctk.CTkLabel(master=tab_view.tab("Notification Settings"), text="Notify me every...") 
        interval_label.pack(pady=5)
        interval_set = ctk.CTkComboBox(master=tab_view.tab("Notification Settings"), values=["15 minutes", "30 minutes", "1 hour", "2 hours", "3 hours", "4 hours", "24 hours"],
                                     command=self.save_settings)
        interval_set.set(self.interval_translator(int(load_settings("Notifications", "scan_interval"))))
        interval_set.pack()

        notify_before = ctk.CTkLabel(master=tab_view.tab("Notification Settings"), text="Only notify expiries happening in the next... (days)")
        notify_before.pack(pady=5)
        notify_entry = ctk.CTkEntry(master=tab_view.tab("Notification Settings"), placeholder_text="Number of days.")
        notify_entry.bind('<Return>', lambda event: current_notify.configure(text=write_settings("Notifications", "notify_days", notify_entry.get())))
        notify_entry.pack(pady=5)
        current_notify_value = self.notification_days()
        current_notify = ctk.CTkLabel(master=tab_view.tab("Notification Settings"), text=current_notify_value)
        current_notify.pack()

        startup_label = ctk.CTkLabel(master=tab_view.tab("Notification Settings"), text="Launch IMPP at system startup?") 
        startup_label.pack(pady=5)
        startup_set = ctk.CTkComboBox(master=tab_view.tab("Notification Settings"), values=["Yes", "No"],
                                     command=self.startup)
        startup_set.set(self.startup_check())
        startup_set.pack()

        # Create layout for About tab
        imp = Image.open(main_icon)
        pict = ctk.CTkImage(light_image=imp, dark_image=imp, size=(100, 100))
        image = ctk.CTkLabel(master=tab_view.tab("About IMPP"), text="", image=pict)
        image.pack()
        text_box = ctk.CTkLabel(master=tab_view.tab("About IMPP"), text="IMPP was written by Ian Nicholls in Python 3.11 \nand is distributed under MIT licence.\nImage assets were developed using AI and edited by Ian Nicholls. ")
        text_box.pack(pady=20)
        github_button = ctk.CTkButton(master=tab_view.tab("About IMPP"), text="GitHub",command= lambda: webbrowser.open("https://github.com/Ian-Nicholls89/exPYre"))
        github_button.pack()

        # Catch when window is closed and allow it to be reopened again later
        self.protocol("WM_DELETE_WINDOW", self.closeEvent)

    def notification_days(self):
        days = load_settings("Notifications", "notify_days")
        return f"Current setting: {days} days."

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
        write_settings("Notifications", "scan_interval", str(choice))
        
    def refresh_databases(self):
        start = databases.get_children().__len__()
        # Clear existing items in the listbox
        for child in databases.get_children():
            databases.delete(child)

        # Add databases back to the listbox and get longest name length
        database_list = load_settings("Databases", None) # placeholder used for key value as not needed to call databases from settings
        column_width = 0
        for name, location in database_list.items():
            databases.insert("", "end", values=(name, location))
            column_width = max(column_width, len(name))
        end = databases.get_children().__len__()
        databases.column("Name", width=column_width) # adjust the column width 

        if not start == 0 and end > start: # if a database has been added then scan new database (assuming here that its the last database in the list)
            for db_name, db_path in reversed(database_list.items()):
                trigger_database_scan({db_name:db_path})
                break            

    def create_database(self):
        # Create new db
        file_path = create_new_db()

        if file_path:
            # Prompt the user to enter a custom name for the database
            custom_name = simpledialog.askstring("Custom Name", "Enter a custom name for the database (optional):\n\n e.g 'PCR Lab Reagents'")
            if not custom_name:
                custom_name = os.path.basename(file_path)  # Use the database file name as the custom name
                    
            # Update the settings file with the new database path and custom name
            write_settings("Databases", custom_name, file_path)
            
            # Refresh the UI to display the new database
            self.refresh_databases()
    
    def load_database(self):
        # User wants to load an existing database
        file_path = filedialog.askopenfilename(title="Select Database File", filetypes=[("Database Files", "*.db")])
        
        if file_path:
            # Prompt the user to enter a custom name for the database
            custom_name = simpledialog.askstring("Custom Name", "Enter a custom name for the database (optional):\n\n e.g 'PCR Lab Reagents'")
            if not custom_name:
                custom_name = os.path.basename(file_path)  # Use the database file name as the custom name
                
            # Update the settings file with the new database path and custom name
            write_settings("Databases", custom_name, file_path)
            
            # Refresh the UI to display the new database
            self.refresh_databases()

    def remove_database(self, name):
            reply = messagebox.askyesno("Confirmation", f"Are you sure you want to delete \"{name[0]}\" database?")
            if reply:
                try:
                    # Remove the database from settings
                    config = configparser.ConfigParser()
                    config.read(SETTINGS)
                    config.remove_option("Databases", name[0])
                    with open(SETTINGS, 'w+') as configfile:
                        config.write(configfile)
                    # Refresh the UI to update the displayed databases
                    self.refresh_databases()
                except ValueError:
                    messagebox.showerror("Error", "Database not found.")
    
    def startup(self, choice):
        startup_shortcut = os.path.join(winshell.startup(), "IMPP.lnk")
        
        if choice == "Yes":
            shell = Dispatch('WScript.Shell')
            startup = shell.CreateShortcut(startup_shortcut)
            startup.TargetPath = os.path.join(os.path.abspath("."), "IMPP.exe")
            startup.WorkingDirectory = os.path.abspath(".")
            startup.save()
        elif choice == "No":
            if os.path.exists(startup_shortcut):
                os.remove(startup_shortcut)
            else:
                return
    
    def startup_check(self):
        if os.path.exists(os.path.join(winshell.startup(), "IMPP.lnk")):
            choice = "Yes"
            return choice
        else:
            choice = "No"
            return choice

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
        database_settings = load_settings("Databases", None) # placeholder used for key value as not needed to call databases from settings

        # Load first database into editing mode
        for name, info in database_settings.items():
            self.switch_database(name, info)
            break

        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        # Create the main window
        self.wm_iconbitmap(main_icon)
        self.geometry("600x400")
        self.title("IMPP - Database Editor")

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
        treeview = ttk.Treeview(master=tab_view.tab("Show All Items"), columns=("Product", "Expiry Date"), show="headings")
        treeview.heading("Product", text="Product")
        treeview.heading("Expiry Date", text="Expiry Date")
        treeview.pack(expand=True, fill="both")
        

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

    # Function to load the database files from the settings file
    def load_settings(self):
        global editor_window
        if not os.path.exists(SETTINGS):
            # If settings file doesn't exist, produce warning and close editor
            messagebox.showwarning("Warning", "No database selected. Please select a database in IMPP settings.")
            editor_window = False
            self.destroy()
        else:
            config = configparser.ConfigParser()
            config.read(SETTINGS)
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
    toaster = WindowsToaster('IMPP')
    newToast = Toast()
    newToast.text_fields = [f"{title}", f"{message}"]
    if "has now expired" in message:
        newToast.AddImage(ToastDisplayImage.fromPath(toast_expired_icon))
    elif "is expiring in" in message:
        newToast.AddImage(ToastDisplayImage.fromPath(toast_alert_icon))    
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

def load_settings(section, key):
    # if settings file doesnt exist, create one, add default settings and continue
    if not os.path.exists(SETTINGS):
        write_settings("Notifications", "scan_interval", str(10800))
        write_settings("Notifications", "notify_days", str(14))
    # start configparser and read the settings file
    config = configparser.ConfigParser()
    config.read(SETTINGS)
    # if the section is of databases then all databases must be read
    if section == "Databases":
        if not config.has_section(section): # if there is no databases in the settings file then none have previously been loaded and at least one must be loaded
            database_path = get_database_path()
            if database_path:
                #  Prompt the user to enter a custom name for the database
                custom_name, _ = QInputDialog.getText(None, "Custom Name", "Enter a custom name for the database (optional):\n\n e.g 'PCR Lab Reagents'")
                if not custom_name:
                    custom_name = os.path.basename(database_path)
                write_settings(section, custom_name, database_path) # write that database into the settings - this will catch and ask if extra databases are to be added
                config.read(SETTINGS) # reread the settings before loading again
                return dict(config[section]) # return all the databases which have been added
        elif config.has_section(section): # if the section exists then proceed with the loading
            if key == None: # if a placeholder key is passed then load all databases
                try:
                    return dict(config[section])
                except KeyError: # bail out of the program if there is a config read error
                    QMessageBox.warning(None, "Warning", "Settings Read Error. Exiting.", QMessageBox.Ok)
                    exit_program()
            else: # return only requested database info
                try:
                    setting = config.get(section, key)
                    return {key:setting,} # if the setting exists then it is returned as a dict
                except KeyError: # bail out of the program if there is a config read error
                    QMessageBox.warning(None, "Warning", "Settings Read Error. Exiting.", QMessageBox.Ok)
                    exit_program()

    # if the section is of notifcation settings then try and get requested key and return it
    else:
        try:
            setting = config.get(section, key)
            return setting # if the setting exists then it is returned
        except KeyError:
            QMessageBox.warning(None, "Warning", "Settings Read Error. Exiting.", QMessageBox.Ok)
            exit_program() # if something goes wrong bail out of the program

def write_settings(section, key, value):
    config = configparser.ConfigParser() # start configparser
    if os.path.exists(SETTINGS): # read the settings file if it exists
        config.read(SETTINGS)
    if not config.has_section(section): # create the settings section if it doesnt exist
            config.add_section(section)

    if section == "Databases" and config.has_option(section, key): # catch when a user is tryng to add a database of a custom name which already exists
        confirm = messagebox.askyesno("Confirmation", "A database by this name already exists. Do you want to overwrite?")
        if confirm: # overwrite if user confirms
            config.set(section, key, value)
            with open (SETTINGS, "w+") as configfile:
                config.write(configfile)
        elif not confirm: # cancel addition if user aborts
            messagebox.showinfo("Database not added.", "The database was not added. Try adding again using a different name.")
            return
    if section == "Databases":
        for name, location in config[section].items():
            if location == value:
                messagebox.showinfo("Database not added.", f"This database already exists under the name \"{name}\"")
                return
    else: # if the setting is anything else then write it (this will overwrite settings in the notification section automatically)
        config.set(section, key, value)
        with open (SETTINGS, "w+") as configfile:
            config.write(configfile)
        if section == "Databases": # if adding a database ask if further databases are to be added
            additional_databases_prompt()
        elif key == "notify_days":
            return SettingsWindow.notification_days(None)
        
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
            custom_name = simpledialog.askstring("Custom Name", "Enter a custom name for the database (optional):\n\n e.g 'PCR Lab Reagents'")
            if not custom_name:
                custom_name = os.path.basename(file_path)  # Use the database file name as the custom name
                
            # Update the settings file with the new database path and custom name
            write_settings("Databases", custom_name, file_path)
        additional_databases_prompt()
    else:
        return

def pause_notifications_24h():
    global notifications_paused
    global pause
    notifications_paused = True

    # Start a timer to resume notifications after 24 hours
    pause = threading.Timer(24 * 60 * 60, resume_notifications)
    pause.start()

    # change submenu text and function to allow for unpausing
    pause_notifications_action.setText("Unpause Notifications")
    pause_notifications_action.triggered.connect(resume_notifications)

def resume_notifications():
    global notifications_paused
    global pause
    notifications_paused = False
    if pause:
        pause.cancel()
    
    # change submenu text and function to allow for pausing 
    pause_notifications_action.setText("Pause Notifications for 24 Hours")
    pause_notifications_action.triggered.connect(pause_notifications_24h)

def trigger_database_scan(database_settings):
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
                    tray_icon.setToolTip("IMPP - an item is nearing expiry")

        # Get past events and show toast notifications if notifications are not paused
        if not notifications_paused:
            past_events = scanner.get_past_events()
            for event in past_events:
                title = f"Expiry in \"{db_name}\""
                message = f"\"{event[1]}\" has now expired"
                show_toast(title, message)

                # update tray icon and tooltip
                tray_icon.setIcon(QIcon(expired_icon))
                tray_icon.setToolTip("IMPP - an item has expired")

        # Close the database connection
        scanner.close()

# Define a function to start a timer for the specified time interval
def start_timer(interval):
    global timer
    # Call perform_database_scan function immediately
    trigger_database_scan(load_settings("Databases", None))
    # Schedule the perform_database_scan function to run periodically at the specified interval
    timer = threading.Timer(interval, start_timer, args=[interval])
    timer.start()

def tray_icon_double_clicked(reason):
    if reason == QSystemTrayIcon.DoubleClick:
        show_editor_window()

def splash(screen_width, screen_height, x, y):
    # create app splash
    splash = ctk.CTk()
    splash.attributes('-transparentcolor', 'gray')
    splash.wm_attributes("-topmost", True)
    pic = Image.open(app_logo)
    splash_width = int(round(pic.width / 2)) 
    splash_height = int(round(pic.height / 2)) 
    splash.overrideredirect(True)
    logo = ctk.CTkImage(light_image=pic, dark_image=pic, size=(splash_width, splash_height)) 
    image = ctk.CTkLabel(splash, text="", image=logo, bg_color="gray")
    image.pack(padx=0, pady=0)

    # Center the window on the screen (might require adjustments based on CTk window manager handling)
    center_x = ((screen_width - int(splash_width)) // 2) + x
    center_y = ((screen_height - int(splash_height)) // 2) + y 
    splash.geometry(f"{splash_width}x{splash_height}+{center_x}+{center_y}")  # Set geometry with position

    # destroy app splash after 5 seconds
    splash.after(5000, splash.quit)
    splash.mainloop()

def exit_program():
    # Cancel the timer if it's running
    global timer
    if timer:
        timer.cancel()

    # Exit the program
    sys.exit()

def main():
    # Extract the scan interval value from settings
    scan_interval = int(load_settings("Notifications", "scan_interval"))  # Defaults to 3 hours

    # Start interval timer with the scan interval
    start_timer(scan_interval)

if __name__ == "__main__":
    for monitor in screeninfo.get_monitors():
        if monitor.is_primary:
            splash(monitor.width, monitor.height, monitor.x, monitor.y)

    # begin creating main app
    app = QApplication(sys.argv)

    # Create a system tray icon
    tray_icon = QSystemTrayIcon()
    tray_icon.setIcon(QIcon(TRAY_ICON))
    tray_icon.setToolTip("IMPP")

    # Create a context menu for the system tray icon
    tray_menu = QMenu()
    scan_action = QAction("Scan Databases Now...", parent=app)
    scan_action.triggered.connect(lambda: trigger_database_scan(load_settings("Databases", None)))
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
