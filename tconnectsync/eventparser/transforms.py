import json
try:
    from static_dicts import ALERTS_DICT, ALARMS_DICT
except ImportError:
    from .static_dicts import ALERTS_DICT, ALARMS_DICT

def enumNameFormat(text):
    if not text:
        return text
    t = text.replace('_', ' ').title().replace(' ', '')
    if t.startswith('no,'):
        return 'No'
    if t.startswith('yes,'):
        return 'Yes'
    
    for i in '-,':
        t = t.split(i)[0]
    
    for i in '()/"\u201c\u201d':
        t = t.replace(i, '')

    return f'{t[0].upper()}{t[1:]}'

def transform_enum(event_def, name, name_fmt, field, tx):
    out = []
    lines_for_out = json.dumps(tx, indent=4).splitlines()
    out += [f'{enumNameFormat(name_fmt)}Map = {lines_for_out[0]}']
    out += lines_for_out[1:]
    out += ['']
    out += [f'class {enumNameFormat(name_fmt)}Enum(Enum):']
    out += [
        f'    {enumNameFormat(v)} = {k}' for k, v in tx.items()
    ]
    out += ['']
    out += [
        '@property',
        f'def {name_fmt}(self):',
        f'    return self.{enumNameFormat(name_fmt)}Enum[self.{name_fmt}Raw]',
        ''
    ]

    return out

def transform_dictionary(event_def, name, name_fmt, field, tx):
    if tx == 'alerts':
        return transform_enum(event_def, name, name_fmt, field, ALERTS_DICT)
    
    if tx == 'alarms':
        return transform_enum(event_def, name, name_fmt, field, ALARMS_DICT)
    return [f'# Dictionary unknown: {tx}']

def transform_bitmask(event_def, name, name_fmt, field, tx):
    out = []
    lines_for_out = json.dumps(tx, indent=4).splitlines()
    out += [f'{enumNameFormat(name_fmt)}Map = {lines_for_out[0]}']
    out += lines_for_out[1:]
    out += ['']
    out += [f'class {enumNameFormat(name_fmt)}Bitmask(IntFlag):',]
    out += [
        f'    {enumNameFormat(v)} = 2**{k}' for k, v in tx.items() if 'unused' not in v.lower()
    ]
    out += ['']
    out += [
        '@property',
        f'def {name_fmt}(self):',
        f'    return self.{enumNameFormat(name_fmt)}Bitmask[self.{name_fmt}Raw]',
        ''
    ]

    return out

def transform_ratio(event_def, name, name_fmt, field, tx):
    out = []
    out += [
        '@property',
        f'def {name_fmt}(self):',
        f'    return self.{name_fmt}Raw * {tx}',
        ''
    ]

    return out



TRANSFORMS = {
    'enum': transform_enum,
    'dictionary': transform_dictionary,
    'bitmask': transform_bitmask,
    'ratio': transform_ratio
}