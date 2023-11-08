import sys


def _gen_zone(**d):
    return '''resource "aws_route53_zone" "primary_domain" {{
  name = "{root_zone}"
}}
'''.format(**d)

def _gen_comment(**d):
    return '''# {line_number}: {line}'''.format(**d)

def _gen_record(**d):
    return '''{tf_line_prefix}resource "aws_route53_record" "primary_domain" {{
{tf_line_prefix}  zone_id = "${{aws_route53_zone.primary_domain.id}}"
{tf_line_prefix}  name    = "{name}"
{tf_line_prefix}  type    = "{type}"
{tf_line_prefix}  records = ["{record}"]
{tf_line_prefix}  ttl     = {ttl}
{tf_line_prefix}}}
'''.format(**d)

if len(sys.argv) < 2:
    print("Usage:\n{0} <zonefile> [--migrates]".format(sys.argv[0]))
    exit(1)

zonefile = sys.argv[1]
migration = False or (True if "--migrate" in " ".join(sys.argv) else False)

with open(zonefile, 'r') as zone_file:
    root_zone = ''
    root_zone_name = ''

    for line_number, line in enumerate(zone_file):
        line = line.strip('\n')
        line_num = line_number + 1
        print(_gen_comment(line_number=line_num, line=line))
        tf_line_prefix = ''

        # skip line if it's not a record
        if ' IN ' not in line:
            print(_gen_comment(line_number=line_num, line="[Skipped] Record is not a valid record: does not have 'IN' identifier.\n\n"))
            continue

        parts = line.split(' ')

        # skip line if it's a comment
        if parts[0] == ";":
            print(_gen_comment(line_number=line_num, line="[Skipped] Record is commented out.\n\n"))
            continue

        # Migration requires NS records to be updated manually
        # to the source hosted zone. The Terraform for this should
        # be written, planned, and deployed manually to control
        # the timing of the cutover.
        if parts[3] == 'NS' and migration:
            print(_gen_comment(line_number=line_num, line="[Disabled] Record requires intention cutover manual action."))
            tf_line_prefix = "# "

        # try and find the root zone
        if parts[3] == 'SOA':
            root_zone = parts[0]
            root_zone_name = root_zone.replace('.','')

            print(_gen_zone(root_zone=root_zone,
                            root_zone_name=root_zone_name))
            continue
        
        record_type = parts[3]

        # remove newline and white characters from record
        # and expand to include the rest of line if type can include spaces
        if record_type in ('MX', 'SRV', 'TXT'):
            record = ' '.join(parts[4:]).strip()
        else:
            record = parts[4].strip()

        # strip the root zone from the end of the string
        if parts[0].endswith('.{0}.'.format(root_zone)):
            record_name = parts[0][:-(len(root_zone) + 2)]
        else:
            record_name = parts[0]

        # skip if provider uses proprietary records for SPF
        if record_type == 'SPF' and not parts[4].find('v=spf'):
            print(_gen_comment(line_number=line_number, line="[Skipped] Record is an invalid SPF record; SPF records are supposed to be TXT records (see next record)."))
            continue

        # strip double quotes if type is txt
        if record_type == 'TXT' and parts[4].startswith('"'):
            record = record[1:-1]

        record_ttl = int(parts[1])

        print(_gen_record(record_name='primary_domain_{1}'.format(parts[0].replace('.',''),parts[3].lower()),
                          name=record_name,
                          tf_line_prefix=tf_line_prefix,
                          ttl=record_ttl,
                          type=record_type,
                          record=record,
                          root_zone_name=root_zone_name))
