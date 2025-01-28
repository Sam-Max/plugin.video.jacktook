import sys
import os
import re

def print_help():
    print("""Usage: python manage_labels.py [operation] [po_file]

Operations:
  replace    Convert numeric labels/help to text strings using PO file
  restore    Convert text labels/help back to numeric IDs using PO file

Required arguments:
  operation   Either 'replace' or 'restore'
  po_file     Path to the strings.po file

Features:
  - Auto-generates missing IDs starting from 30800 during restore
  - Creates .missing.po file for unresolved strings during restore
  - Handles both label and help attributes
  - Preserves empty strings and existing numeric IDs
  - Maintains XML structure and formatting""")
    sys.exit(0)

def parse_po(po_file):
    id_to_msg = {}
    msg_to_id = {}
    existing_ids = set()
    current_id = current_msg = None
    
    with open(po_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('msgctxt'):
                current_id = line.split('"')[1][1:]  # Extract number after #
                existing_ids.add(current_id)
            elif line.startswith('msgid'):
                current_msg = line.split('"')[1]
            elif line == '':
                if current_id and current_msg:
                    id_to_msg[current_id] = current_msg
                    msg_to_id[current_msg] = current_id
                current_id = current_msg = None
        
        if current_id and current_msg:
            id_to_msg[current_id] = current_msg
            msg_to_id[current_msg] = current_id
            existing_ids.add(current_id)
            
    return id_to_msg, msg_to_id, existing_ids

def process_restore(content, msg_to_id, existing_ids, po_file):
    missing_entries = {}
    current_new_id = 30800
    existing_ids = set(map(int, existing_ids))  # Convert to integers
    
    # Find all text labels that need replacement
    matches = re.findall(r'(label|help)="(.*?)"', content)
    text_labels = {m[1] for m in matches if not m[1].isdigit() and m[1] not in msg_to_id and m[1]}
    
    # Assign new IDs to missing entries
    for text in text_labels:
        while current_new_id in existing_ids:
            current_new_id += 1
        missing_entries[text] = current_new_id
        existing_ids.add(current_new_id)
        current_new_id += 1
    
    # Replace text labels with IDs
    def replacer(m):
        attr_type = m.group(1)
        text = m.group(2)
        if text == "": return f'{attr_type}=""'
        if text.isdigit(): return f'{attr_type}="{text}"'
        return f'{attr_type}="{msg_to_id.get(text, missing_entries.get(text, "XXXXX"))}"'
    
    new_content = re.sub(r'(label|help)="(.*?)"', replacer, content)
    
    # Generate missing.po file if needed
    if missing_entries:
        po_dir = os.path.dirname(po_file)
        po_name = os.path.splitext(os.path.basename(po_file))[0]
        missing_path = os.path.join(po_dir, f"{po_name}.missing.po")
        
        with open(missing_path, 'w', encoding='utf-8') as f:
            for text, num_id in sorted(missing_entries.items(), key=lambda x: x[1]):
                f.write(f'msgctxt "#{num_id}"\nmsgid "{text}"\nmsgstr ""\n\n')
    
    return new_content

def process_replace(content, id_to_msg):
    return re.sub(
        r'(label|help)="(\d+)"',
        lambda m: f'{m.group(1)}="{id_to_msg.get(m.group(2), m.group(2))}"',
        content
    )

def main():
    if '-h' in sys.argv or len(sys.argv) != 3:
        print_help()

    operation, po_file = sys.argv[1].lower(), sys.argv[2]
    
    if operation not in ('replace', 'restore'):
        print(f"Invalid operation: {operation}")
        print_help()

    # Validate paths
    input_xml = f'resources/settings{"_strings" if operation == "restore" else ""}.xml'
    output_xml = f'resources/settings{"_strings" if operation == "replace" else ""}.xml'
    
    if not os.path.exists(input_xml):
        print(f"Input file not found: {input_xml}")
        sys.exit(1)
        
    if not os.path.exists(po_file):
        print(f"PO file not found: {po_file}")
        sys.exit(1)

    # Process files
    try:
        with open(input_xml, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if operation == 'replace':
            id_to_msg, _, _ = parse_po(po_file)
            new_content = process_replace(content, id_to_msg)
        else:
            _, msg_to_id, existing_ids = parse_po(po_file)
            new_content = process_restore(content, msg_to_id, existing_ids, po_file)
        
        os.makedirs(os.path.dirname(output_xml), exist_ok=True)
        with open(output_xml, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        print(f"Successfully generated {output_xml}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()