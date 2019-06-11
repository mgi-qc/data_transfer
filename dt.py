import sys
import os
import csv
import argparse
import glob
import subprocess
import smartsheet
from datetime import datetime,timedelta

API_KEY = os.environ.get('SMRT_API')

if API_KEY is None:
    sys.exit('Api key not found')

smart_sheet_client = smartsheet.Smartsheet(API_KEY)
smart_sheet_client.errors_as_exceptions(True)

mm_dd_yy = datetime.now().strftime('%Y-%m-%d')
exp_date = (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')


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
parser.add_argument('-ub', help='Uses Gerald Bam Path for transfer files', action='store_true')
parser.add_argument('-ab', type=str, help='User input file dir for transfer')
args = parser.parse_args()

cwd = os.getcwd()

if not os.path.isfile(args.f):
    sys.exit('{} file not found'.format(args.f))

disc_space_in = subprocess.check_output(['df', '-h', '/gscmnt/gxfer1/gxfer1']).decode('utf-8')
print('\nCurrent disk status:')
print(disc_space_in)

disc_in = input('Is there adequate disk space?(y/n): ')

while True:
    if disc_in == 'n':
        sys.exit('Insufficient disk space.')
    elif disc_in == 'y':
        break
    else:
        disc_in = input('Please enter either y or n: ')

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


def write_samplemap(path_samp, dtdir):
    dt_file = dtdir.lower().replace('-', '')
    
    with open(dt_file, 'a') as df:
        df.write(path_samp)


def gxfr_command(dtdir):

    while True:
        dt_file = dtdir.lower().replace('-', '')
        tag = input('\nEnter data transfer subject line:\n').strip().replace(' ', '\ ')
        input_emails = input('\nEnter data transfer emails (comma separated list):\n')
        input_emails = input_emails + ',dt@jira.ris.wustl.edu'
        command = 'gxfer-upload-md5 --file={} --tag="{}\ {}" --emails={}\n'.format(dt_file, tag, dt_dir, input_emails)

        if 'y' in input('\ngxfer command:\n{}\ny to continue (anything else to re-create):\n'.format(command)).lower():
            with open('gxfer.data.transfer.sh', 'w') as gx:
                gx.write(command)
                print('\nData transfer setup complete.')
                print('{} Samples ready for transfer.'.format(sample_count))
                print('Transfer directory:\n{}'.format(os.path.abspath(os.getcwd())))
                return input_emails


def md5_check(md5_dir, sample, nu_check):
    search_type = '*.gz.md5'

    if args.ub:
        search_type = '*.bam.md5'
    if len(glob.glob('{}/{}'.format(md5_dir, search_type))) != nu_check:
        print('{} md5 files are missing from {}'.format(sample, md5_dir))


with open(args.f, 'r') as infiletsv, open('Samplemap.csv', 'w') as sf:

    fh = csv.DictReader(infiletsv, delimiter='\t')
    infile_header = fh.fieldnames

    if not (args.ub or args.ab):
        infile_header.extend(['File1', 'File2'])

    sm = csv.DictWriter(sf, fieldnames=infile_header, delimiter=',')
    sm.writeheader()

    md5_missing_file_dict = {}
    sample_count = 0

    for line in fh:

        sample_count += 1

        if not (args.ub or args.ab):

            if not os.path.isdir(line['Full Path']):
                print('{} directory not found.'.format(line['Full Path']))
                continue

            paths(line['Full Path'], dt_dir)
            md5_check(line['Full Path'], line['Sample Full Name'], 2)
            fq_files = glob.glob('{}/*fastq*'.format(line['Full Path']))
            file_count = 1

            for file in fq_files:
                fastq = file.split('/')[-1]

                if 'md5' not in fastq:
                    line['File{}'.format(file_count)] = fastq
                    file_count += 1

            sm.writerow(line)

        if args.ub:

            if os.path.isfile(line['Gerald Bam Path']):
                md5_check(os.path.dirname(line['Gerald Bam Path']), line['Sample Full Name'], 1)
                with open(dt_dir.lower().replace('-', ''), 'a') as fh:
                    fh.write('{}\n'.format(line['Gerald Bam Path']))
            else:
                print('{} file not found.'.format(line['Gerald Bam Path']))

            sm.writerow(line)

        if args.ab:
            sm.writerow(line)

if args.ab:
    if os.path.isdir(args.ab):
        with open(dt_dir.lower().replace('-', ''), 'a') as fh:
            fh.write('{}*\n'.format(args.ab))
    else:
        sys.exit('{} directory not found'.format(args.b))

write_samplemap(os.path.realpath('Samplemap.csv'), dt_dir)

emails = gxfr_command(dt_dir)

#Updating smartsheet:
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
