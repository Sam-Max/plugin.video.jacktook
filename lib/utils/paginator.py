import json
from lib.api.trakt.base_cache import connect_database


class Paginator:
    def __init__(self, page_size=10):
        self.page_size = page_size
        self.total_pages = 0
        self.current_page = 0

    def _connect(self):
        return connect_database(database_name="paginator_db")

    def _store_page(self, page_number, total_pages, data):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO paginated_data (id, page_number, data, total_pages)
            VALUES (?, ?, ?, ?)
        ''', (f'page_{page_number}', page_number, json.dumps(data), total_pages))
        conn.commit()
        conn.close()

    def _retrieve_page(self, page_number):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT data FROM paginated_data WHERE page_number = ?
        ''', (page_number,))
        result = cursor.fetchone()
        conn.close()
        if result and result[0] is not None:
            return json.loads(result[0])
        return None
    
    def _clear_table(self):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM paginated_data')
        conn.commit()
        conn.close()
        
    def initialize(self, data):
        self._clear_table() 
        self.total_pages = (len(data) + self.page_size - 1) // self.page_size
        for i in range(self.total_pages):
            start = i * self.page_size
            end = start + self.page_size
            page_data = data[start:end]
            self._store_page(i + 1, self.total_pages, page_data)

    def get_page(self, page_number):
        self.current_page = page_number - 1
        data = self._retrieve_page(page_number)
        if data is None:
            raise IndexError("Page number not found in database: Requested page {}".format(page_number))
        return data

    def next_page(self):
        """Move to the next page."""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
        return self.get_page(self.current_page + 1)

    def previous_page(self):
        """Move to the previous page."""
        if self.current_page > 0:
            self.current_page -= 1
        return self.get_page(self.current_page + 1)

    def current_page_data(self):
        """Get the data for the current page."""
        return self.get_page(self.current_page + 1)



paginator_db = Paginator()
