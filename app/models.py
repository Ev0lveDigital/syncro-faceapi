# This file can be used for defining data structures or helper functions related to data handling.
    # Since we're using direct SQL, this file might not be strictly necessary for defining ORM models.

    # Example helper function to format date/time:
    def format_datetime(dt):
        if dt:
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        return ""
