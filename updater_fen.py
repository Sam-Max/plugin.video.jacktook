# -*- coding: utf-8 -*-
import json
import requests
import shutil
from os import path
from caches.settings_cache import get_setting, set_setting
from modules.utils import string_alphanum_to_num, unzip
from modules import kodi_utils 
logger = kodi_utils.logger

def get_location(insert=''):
	return 'https://github.com/%s/%s/raw/main/packages/%s' % (get_setting('fenlight.update.username'), get_setting('update.location'), insert)

def get_versions():
	try:
		result = requests.get(get_location('fen_light_version'))
		if result.status_code != 200: return None, None
		online_version = result.text.replace('\n', '')
		current_version = kodi_utils.addon_version()
		return current_version, online_version
	except: return None, None

def get_changes(online_version=None):
	try:
		if not online_version:
			current_version, online_version = get_versions()
			if not version_check(current_version, online_version): return kodi_utils.ok_dialog(heading='Fen Light Updater',
				text='You are running the current version of Fen Light.[CR][CR]There is no new version changelog to view.')
		kodi_utils.show_busy_dialog()
		result = requests.get(get_location('fen_light_changes'))
		kodi_utils.hide_busy_dialog()
		if result.status_code != 200: return kodi_utils.notification('Error', icon=kodi_utils.get_icon('downloads'))
		changes = result.text
		return kodi_utils.show_text('New Online Release (v.%s) Changelog' % online_version, text=changes, font_size='large')
	except:
		kodi_utils.hide_busy_dialog()
		return kodi_utils.notification('Error', icon=kodi_utils.get_icon('downloads'))

def version_check(current_version, online_version):
	return string_alphanum_to_num(current_version) != string_alphanum_to_num(online_version)

def update_check(action=4):
	if action == 3: return
	current_version, online_version = get_versions()
	if not current_version: return
	show_after_action = True
	if not version_check(current_version, online_version):
		if action == 4: return kodi_utils.ok_dialog(heading='Fen Light Updater', text='Installed Version: [B]%s[/B][CR]Online Version: [B]%s[/B][CR][CR] %s' \
			% (current_version, online_version, '[B]No Update Available[/B]'))
		return
	if action in (0, 4):
		if not kodi_utils.confirm_dialog(heading='Fen Light Updater', text='Installed Version: [B]%s[/B][CR]Online Version: [B]%s[/B][CR][CR] %s' \
			% (current_version, online_version, '[B]An Update is Available[/B][CR]Perform Update?'), ok_label='Yes', cancel_label='No'): return
		if kodi_utils.confirm_dialog(heading='Fen Light Updater', text='Do you want to view the changelog for the new release before installing?', ok_label='Yes', cancel_label='No'):
			get_changes(online_version)
			if not kodi_utils.confirm_dialog(heading='Fen Light Updater', text='Continue with Update After Viewing Changes?', ok_label='Yes', cancel_label='No'): return
			show_after_action = False
	if action == 1: kodi_utils.notification('Fen Light Update Occuring', icon=kodi_utils.get_icon('downloads'))
	elif action == 2: return kodi_utils.notification('Fen Light Update Available', icon=kodi_utils.get_icon('downloads'))
	return update_addon(online_version, action, show_after_action)

def rollback_check():
	current_version = get_versions()[0]
	url = 'https://api.github.com/repos/%s/%s/contents/packages' % (get_setting('update.username'), get_setting('update.location'))
	kodi_utils.show_busy_dialog()
	results = requests.get(url)
	kodi_utils.hide_busy_dialog()
	if results.status_code != 200: return kodi_utils.ok_dialog(heading='Fen Light Updater', text='Error rolling back.[CR]Please install rollback manually')
	results = results.json()
	results = [i['name'].split('-')[1].replace('.zip', '') for i in results if 'plugin.video.fenlight' in i['name'] \
				and not i['name'].split('-')[1].replace('.zip', '') == current_version]
	if not results: return kodi_utils.ok_dialog(heading='Fen Light Updater', text='No previous versions found.[CR]Please install rollback manually')
	results.sort(reverse=True)
	list_items = [{'line1': item, 'icon': kodi_utils.get_icon('downloads')} for item in results]
	kwargs = {'items': json.dumps(list_items), 'heading': 'Choose Rollback Version'}
	rollback_version = kodi_utils.select_dialog(results, **kwargs)
	if rollback_version == None: return
	if not kodi_utils.confirm_dialog(heading='Fen Light Updater',
		text='Are you sure?[CR]Version [B]%s[/B] will overwrite your current installed version.[CR]Fen Light will set your update action to [B]OFF[/B] if rollback is successful' \
		% rollback_version): return
	update_addon(rollback_version, 5)

def update_addon(new_version, action, show_after_action=True):
	kodi_utils.close_all_dialog()
	kodi_utils.execute_builtin('ActivateWindow(Home)', True)
	kodi_utils.notification('Fen Light Performing Rollback' if action == 5 else 'Fen Light Performing Update', icon=kodi_utils.get_icon('downloads'))
	zip_name = 'plugin.video.fenlight-%s.zip' % new_version
	url = get_location('%s') % zip_name
	kodi_utils.show_busy_dialog()
	result = requests.get(url, stream=True)
	kodi_utils.hide_busy_dialog()
	if result.status_code != 200: return kodi_utils.ok_dialog(heading='Fen Light Updater', text='Error Updating.[CR]Please install new update manually')
	zip_location = path.join(kodi_utils.translate_path('special://home/addons/packages/'), zip_name)
	with open(zip_location, 'wb') as f: shutil.copyfileobj(result.raw, f)
	shutil.rmtree(path.join(kodi_utils.translate_path('special://home/addons/'), 'plugin.video.fenlight'))
	success = unzip(zip_location, kodi_utils.translate_path('special://home/addons/'), kodi_utils.translate_path('special://home/addons/plugin.video.fenlight/'))
	kodi_utils.delete_file(zip_location)
	if not success: return kodi_utils.ok_dialog(heading='Fen Light Updater', text='Error Updating.[CR]Please install new update manually')
	if action == 5:
		set_setting('update.action', '3')
		kodi_utils.ok_dialog(heading='Fen Light Updater', text='[CR]Success.[CR]Fen Light rolled back to version [B]%s[/B]' % new_version)
	elif action in (0, 4):
		if show_after_action:
			if kodi_utils.confirm_dialog(heading='Fen Light Updater', text='[CR]Success.[CR]Fen Light updated to version [B]%s[/B]' % new_version,
										ok_label='Changelog', cancel_label='Exit', default_control=10) != False:
				kodi_utils.show_text('Changelog', file=kodi_utils.translate_path('special://home/addons/plugin.video.fenlight/resources/text/changelog.txt'), font_size='large')
		else:
			kodi_utils.ok_dialog(heading='Fen Light Updater', text='[CR]Success.[CR]Fen Light updated to version [B]%s[/B]' % new_version)
	kodi_utils.update_local_addons()
	kodi_utils.disable_enable_addon()
	kodi_utils.update_kodi_addons_db()
	kodi_utils.refresh_widgets()
