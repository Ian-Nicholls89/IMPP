IMPP was born out of a desire to learn coding and a lot of frustration with spreadsheets. 
I work across multiple labs each of which has short shelf life consumables and I get tired of endless spreadsheets that needed constant checking. 
I wanted a 'set and forget' software where I could add consumables and be reminded when they are expired/nearing expiry. Thats where IMPP comes in.


IMPP is your personal Daemon (get it?) which will keep track of your stuff. It's a program written in python in which the user creates one or many SQLite3 databases, gives them a name such as a room number or task which groups products together and starts adding products and their expiry dates to.
IMPP will then scan those databases automatically in the background and give a windows toast telling notifying which item in which database is approaching expiry, or has already expired.

