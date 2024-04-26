# compile using pyinstaller --windowed --onefile --icon=assets/petri-dish96.ico --hidden-import babel.numbers exPYreGUI.py
import configparser
import customtkinter as ctk
import os
import sys
from tkcalendar import Calendar
from tkinter import ttk, messagebox
import sqlite3

main_dir = os.path.dirname(os.path.abspath(__file__))
icon = os.path.join(main_dir, "assets", "petri-dish96.ico")

# Define global variables
SETTINGS_FILE = os.path.join(main_dir, "database_settings.ini")

# Function to load the database files from the settings file created in main program
def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        # If settings file doesn't exist, produce warning and close editor
        messagebox.showwarning("Warning", "No database selected. Please select a database in exPYre settings.")
        sys.exit()
    else:
        config = configparser.ConfigParser()
        config.read(SETTINGS_FILE)
        try:
            return dict(config['Settings'])
        except KeyError:
            messagebox.showwarning("Warning", "Settings read error. Exiting editor.")
            sys.exit()

def fetch_data():
    # fetch all data
    global items
    conn = sqlite3.connect(db_location)
    c = conn.cursor()
    c.execute("SELECT * FROM products")
    items = c.fetchall()
    conn.close()

    return items

def populate_treeview(products):
    # Clear existing items in the treeview
    for item in treeview.get_children():
        treeview.delete(item)

    # Add new products to the treeview
    for id, product, expiry_date in products:
        treeview.insert("", "end", values=(product, expiry_date))

def database_dropdown():
    global db_names
    db_names = []
    for name, info in database_settings.items():
        db_names.append(name)

def change_database_dropdown(name):
    global db_location
    if name in database_settings:
        db_location = database_settings[name]
        populate_treeview(fetch_data())

# Function to delete selected item
def delete_item():
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
                populate_treeview(fetch_data())
            except ValueError:
                messagebox.showerror("Error", "Item not found in treeview.")

def create_gui():
    global treeview
    global product_name_entry
    global calendar
    # Create the main window
    app = ctk.CTk()
    app.wm_iconbitmap(icon)
    app.geometry("600x400")
    app.title("exPYre - Database Editor")

    # Create a dropdown menu
    database_dropdown()
    dropdown = ctk.CTkOptionMenu(app, values=list(db_names), command=change_database_dropdown)
    dropdown.pack(padx=10, pady=10)

    # Create a CTkTabview for managing tabs
    tab_view = ctk.CTkTabview(master=app)
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
    populate_treeview(fetch_data())

    # Create the delete button
    delete_button = ctk.CTkButton(master=tab_view.tab("Show All Items"), text="Delete Selected", command=delete_item)
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
    add_button = ctk.CTkButton(master=tab_view.tab("Add Products"), text="Add Product", command=add_product)
    add_button.pack()

    # Run the main loop
    app.mainloop()

def add_product():
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
    populate_treeview(fetch_data())
    

# Function to switch to a selected database
def switch_database(name, info):
    global db_location
    db_location = info

if __name__ == "__main__":
    # Load all databases from settings file
    database_settings = load_settings()

    # Load first database into editing mode
    for name, info in database_settings.items():
        switch_database(name, info)
        break

    create_gui()
