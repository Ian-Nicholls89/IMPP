exPYre was born out of a desire to learn coding and a lot of frustration with spreadsheets. 
I work across multiple labs each of which has short shelf life consumables and I get tired of endless spreadsheets that needed constant checking. 
I wanted a 'set and forget' software where I could add consumables and be reminded when they are expired/nearing expiry. Thats where exPYre comes in.


exPYre is a small program written in python in which the user creates a SQLite3 database gives that a name and starts adding products and their expiry dates to.
The system tray daemon will then scan those databases in the background perdiodically and give you a windows toast telling you which item in which database is approaching expiry.

