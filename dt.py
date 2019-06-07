import sys
import os
import csv
import argparse
import glob
import subprocess
import smartsheet
from datetime import datetime,timedelta

smart_sheet_client = smartsheet.Smartsheet('bumf4jd6jv71w4ic1w4dnlbjgj')
smart_sheet_client.errors_as_exceptions(True)

mm_dd_yy = datetime.now().strftime('%m%d%y')
exp_date = (datetime.now() + timedelta(days=14)).strftime('%m%d%y')

def get_object(object_id, object_tag):

    if object_tag == 'f':
        obj = smart_sheet_client.Folders.get_folder(str(object_id))
    elif object_tag == 'w':
        obj = smart_sheet_client.Workspaces.get_workspace(str(object_id))
    elif object_tag == 's':
        obj = smart_sheet_client.Sheets.get_sheet(str(object_id))
    return obj


parser = argparse.ArgumentParser()
parser.add_argument('-f', type=str, help='Illumina bam path tsv from imp', required=True)
args = parser.parse_args()

cwd = os.getcwd()

disc_space_in = subprocess.check_output('df', '-h', '/gscmnt/gxfer1/gxfer1').decode('utf-8')
print('Current disk status: \n')
print(disc_space_in)

disc_in = input('\nIs there adequate disk space?(y/n): ')

while True:
    if disc_in == 'n':
        sys.exit('Insufficient disk space.')
    elif disc_in == 'y':
        break
    else:
        disc_in = input('Please enter either y or n: ')


if not os.path.isfile(args.f):
    sys.exit('{} file not found'.format(args.f))

dt_dir = input('\nInput data transfer directory (JIRA ticket number):\n').strip()

if os.path.isdir(dt_dir):
    sys.exit('Exiting: {} directory already exists.'.format(dt_dir))
else:
    os.mkdir(dt_dir)
    os.rename(os.path.join(cwd, args.f), os.path.join(cwd, dt_dir, args.f))
    os.chdir(dt_dir)


def paths(indir, dtdir):
    dt_file = dtdir.lower().replace('-', '')

    with open('paths', 'a') as p, open(dt_file, 'a') as df:
        p.write('{}\n'.format(indir))
        df.write('{}/*fastq*\n'.format(indir))


def gxfr_command(dtdir):

    while True:
        dt_file = dtdir.lower().replace('-', '')
        tag = input('\nEnter data transfer subject line:\n').strip().replace(' ', '\ ')
        emails = input('\nEnter data transfer emails (comma separated list):\n')
        command = 'gxfer-upload-md5 --file={} --tag="{}\ {}" --emails={}\n'.format(dt_file, tag, dt_dir, emails)

        if 'y' in input('\ngxfer command:\n{}\ny to continue (anything else to re-create):\n'.format(command)).lower():
            with open('gxfer.data.transfer.sh', 'w') as gx:
                gx.write(command)
                print('Data transfer setup complete.')
                return emails


with open(args.f, 'r') as infiletsv, open('Samplemap.csv', 'w') as sf:

    fh = csv.DictReader(infiletsv, delimiter='\t')
    infile_header = fh.fieldnames
    infile_header.append('Files')

    sm = csv.DictWriter(sf, fieldnames=infile_header, delimiter=',')
    sm.writeheader()

    md5_missing_file_dict = {}

    for line in fh:

        if not os.path.isdir(line['Full Path']):
            print('{} directory not found.'.format(line['Full Path']))
            continue

        paths(line['Full Path'], dt_dir)

        fq_files = glob.glob('{}/*fastq*'.format(line['Full Path']))

        file_field = ''
        print(fq_files)
        md5_check = 0

        for file in fq_files:
            print('test1')
            fastq = file.split('/')[-1]
            if 'md5' not in fastq:
                file_field += fastq + ' '
            else:
                md5_check += 1

        line['Files'] = file_field.rstrip()

        sm.writerow(line)

        if md5_check != 2:
            md5_missing_file_dict[line['Sample Full Name']] = line['Full Path']
            
        line['Files'] = file_field.rstrip()
        sm.writerow(line)

if len(md5_missing_file_dict) > 0:
  for sample in md5_missing_file_dict:
      print('Samples are missing md5 files:\n' + sample + '\t' + md5_missing_file_dict[sample])

emails = gxfr_command(dt_dir)


#Building Smartsheet:

"""WORK IN PROGRESS"""

data_transfer_sheet = get_object(33051905419140, 's')

columns = data_transfer_sheet.columns
column_dict = {}

for column in columns:
    column_dict[column.title] = column.id

new_row = smartsheet.models.Row()
new_row.to_bottom = True
new_row.cells.append({'column_id' : column_dict['JIRA ID'],'value' : dt_dir})
new_row.cells.append({'column_id' : column_dict['Transfer Date'], 'value' : mm_dd_yy})
new_row.cells.append({'column_id' : column_dict['Data Transfer Expiration'], 'value' : exp_date})
new_row.cells.append({'column_id' : column_dict['Collaborator Email'], 'value' : emails})

response = smart_sheet_client.Sheets.add_rows(data_transfer_sheet.id, new_row)