import datetime

years_tvshows = [{'name': '2024', 'id': 2024}]

def get_dates(days, reverse=True):
    current_date = get_current_date(return_str=False)
    if reverse: 
        new_date = (current_date - datetime.timedelta(days=days)).strftime('%Y-%m-%d')
    else: 
        new_date = (current_date + datetime.timedelta(days=days)).strftime('%Y-%m-%d')
    return str(current_date), new_date

def get_current_date(return_str=True):
	if return_str: return str(datetime.date.today())
	else: return datetime.date.today()