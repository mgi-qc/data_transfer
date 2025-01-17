import sys
import os
import csv
import argparse
import glob
import subprocess
import smartsheet
from datetime import datetime, timedelta

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
parser.add_argument('-f', type=str, help='Illumina bam path csv from imp (required)', required=True)
parser.add_argument('-gb', help='Uses Gerald Bam Path for transfer files', action='store_true')
parser.add_argument('-i', help='Uses Index Sequence to find fastq files', action='store_true')
parser.add_argument('-t', help='input file format is tsv (default=csv)', action='store_true')
parser.add_argument('-ud', type=str, help='User input dir for file transfer')
parser.add_argument('-c', help='cellRanger data transfer', action='store_true')
args = parser.parse_args()

cwd = os.getcwd()

if not os.path.isfile(args.f):
    sys.exit('{} file not found'.format(args.f))

disc_space_in = subprocess.check_output(['df', '-h', '/gscmnt/gxfer1/gxfer1']).decode('utf-8')
print('\nCurrent disk status:')
print(disc_space_in)

# Turned off, user can quit if there's inadequate disk space.
# disc_in = input('Is there adequate disk space?(y/n): ')
#
# while True:
#     if disc_in == 'n':
#         sys.exit('Insufficient disk space.')
#     elif disc_in == 'y':
#         break
#     else:
#         disc_in = input('Please enter either y or n: ')

while True:
    dt_dir = input('Input data transfer directory (JIRA ticket number, "-" required in dir name):\n').strip()
    if '-' not in dt_dir:
        continue
    else:
        break

if os.path.isdir(dt_dir):
    sys.exit('Exiting: {} directory already exists.'.format(dt_dir))
else:
    os.mkdir(dt_dir)
    os.rename(os.path.join(cwd, args.f), os.path.join(cwd, dt_dir, args.f))
    os.chdir(dt_dir)


def paths(indir, dtdir, index=None):
    dt_file = dtdir.lower().replace('-', '')

    with open('paths', 'a') as p, open(dt_file, 'a') as d:
        p.write('{}\n'.format(indir))
        if args.i:
            d.write('{}/{}*_R*fastq*\n'.format(indir, index))
        else:
            d.write('{}/*fastq*\n'.format(indir))


def write_samplemap(path_samp, dtdir):
    dt_file = dtdir.lower().replace('-', '')
    
    with open(dt_file, 'a') as df:
        df.write(path_samp)


def gxfr_command(dtdir):

    while True:
        dt_file = dtdir.lower().replace('-', '')
        tag = input('\nEnter data transfer subject line:\n').strip().replace(' ', '\ ')
        input_emails = input('\nEnter data transfer emails (comma separated list):\n')
        input_emails = input_emails + ',lmaguire,dt@jira.ris.wustl.edu'
        command = 'gxfer-upload-md5 --file={} --tag="{}\ {}" --emails={}\n'.format(dt_file, tag, dt_dir, input_emails)

        if 'y' in input('\ngxfer command:\n{}\ny to continue (anything else to re-create):\n'.format(command)).lower():
            if args.gb and dup_check:
                with open('gxfer.data.transfer.symlink.sh', 'w') as gxs:
                    sym_command = 'gxfer-upload-md5 --file={} --tag="{}\ {}" --emails={}\n'.format(
                        '{}.symlink'.format(dt_file), tag, dt_dir, input_emails)
                    print('\nSymbolic link gxfer command for duplicate bams:\n{}'.format(sym_command))
                    gxs.write(sym_command)

            with open('gxfer.data.transfer.sh', 'w') as gx:
                gx.write(command)
                print('\nData transfer setup complete.')
                print('{} Samples ready for transfer.'.format(sample_count))
                print('Transfer directory:\n{}'.format(os.path.abspath(os.getcwd())))
                return input_emails


def md5_check(md5_dir, sample, nu_check):
    search_type = '*.gz.md5'

    if args.gb:
        search_type = '*.bam.md5'
    if len(glob.glob('{}/{}'.format(md5_dir, search_type))) != nu_check:
        print('{} md5 files are missing from {}'.format(sample, md5_dir))


if args.c:
    with open('{}.cellRanger.tar.sh'.format(dt_dir), 'w') as f, open(dt_dir.lower().replace('-', ''), 'a') as df:
        while True:
            sample_name = input('\ncellRanger sample name:\n') + '.tar.gz'
            df.write('{}\n'.format(os.path.join(cwd, sample_name)))
            f.write('tar -czvf {} {}\n'.format(sample_name, input('cellRanger data directory:\n')))
            if 'n' in input('\nEnter additional cellRanger samples? (y/n):\n').lower():
                break


with open(args.f, 'r') as infiletsv, open('Samplemap.csv', 'w') as sf:

    delim = ','
    if args.t:
        delim = '\t'

    fh = csv.DictReader(infiletsv, delimiter=delim)
    infile_header = fh.fieldnames

    if not (args.gb or args.ud):
        infile_header.extend(['File1', 'File2'])

    sm = csv.DictWriter(sf, fieldnames=infile_header, delimiter=',')
    sm.writeheader()

    md5_missing_file_dict = {}
    dup_status = False
    dup_check = {}
    sample_count = 0

    for line in fh:

        sample_count += 1

        if not (args.gb or args.ud):

            if 'Full Path' not in line or 'Index Sequence' not in line or 'Sample Full Name' not in line:
                sys.exit('Header fields not correct, please check input file headers: Full Path Index, Sequence, '
                         'Sample, Full Name are present')

            if not os.path.isdir(line['Full Path']):
                print('Sample: {}, {} directory not found.'.format(line['Sample Full Name'], line['Full Path']))
                continue

            paths(line['Full Path'], dt_dir, index=line['Index Sequence'])
            md5_check(line['Full Path'], line['Sample Full Name'], 2)
            fq_files = glob.glob('{}/*fastq*'.format(line['Full Path']))
            if args.i:
                fq_files = glob.glob('{}/{}*_R*fastq*'.format(line['Full Path'], line['Index Sequence']))
            file_count = 1

            for file in fq_files:

                fastq = file.split('/')[-1]

                if 'md5' not in fastq:
                    if file_count > 2:
                        sys.exit('More than 2 fastq files match to {}'.format(fastq))
                    line['File{}'.format(file_count)] = fastq
                    file_count += 1

            sm.writerow(line)

        if args.gb:

            if 'Gerald Bam Path' not in line:
                sys.exit('Gerald Bam Path header not found, please check header is named correctly')

            if os.path.isfile(line['Gerald Bam Path']):
                md5_check(os.path.dirname(line['Gerald Bam Path']), line['Sample Full Name'], 1)

                if '.bam' in line['Gerald Bam Path']:
                    bam_file = line['Gerald Bam Path'].split('/')[-1]
                    if bam_file not in dup_check:
                        dup_check[bam_file] = bam_file
                    else:
                        dup_status = True

                with open(dt_dir.lower().replace('-', ''), 'a') as fh:
                    fh.write('{}\n'.format(line['Gerald Bam Path']))
            else:
                print('Bam file not found:\n{}'.format(line['Gerald Bam Path']))
                print(line, '\n')

            sm.writerow(line)

        if args.ud:
            sm.writerow(line)

if args.ud:

    if not os.path.isdir(args.ud):
        sys.exit('{} directory not found'.format(args.ud))

    with open(dt_dir.lower().replace('-', ''), 'a') as fh:
        fh.write('{}*\n'.format(args.ud))


if dup_status:
    with open('Samplemap.csv', 'r') as sm, open('Samplemap.symlink.csv', 'w') as ss, \
            open('{}.symlink'.format(dt_dir.lower().replace('-', '')), 'w') as dts:

        sm_csv = csv.DictReader(sm)
        sm_header = sm_csv.fieldnames
        sm_header.append('bam_symlink_path')

        ss_csv = csv.DictWriter(ss, fieldnames=sm_header)
        ss_csv.writeheader()

        if not os.path.isdir('symlink'):
            os.mkdir('symlink')

        for line in sm_csv:
            if line['Gerald Bam Path'] and 'bam' in line['Gerald Bam Path']:
                bamfile_path_split = line['Gerald Bam Path'].split('/')
                symlink_file = '{}/symlink/{}.{}'.format(os.getcwd(), bamfile_path_split[-2], bamfile_path_split[-1])
                if not os.path.islink(symlink_file):
                    os.symlink(line['Gerald Bam Path'], symlink_file)
                    line['bam_symlink_path'] = symlink_file
                    ss_csv.writerow(line)
                    dts.write('{}\n'.format(symlink_file))
                else:
                    print('{} symlink path already exists.'.format(symlink_file))

        dts.write('Samplemap.symlink.csv')


write_samplemap(os.path.realpath('Samplemap.csv'), dt_dir)
emails = gxfr_command(dt_dir)

# Updating smartsheet:
data_transfer_sheet = get_object(33051905419140, 's')

columns = data_transfer_sheet.columns
column_dict = {}

for column in columns:
    column_dict[column.title] = column.id

new_row = smartsheet.models.Row()
new_row.to_bottom = True
new_row.cells.append({'column_id': column_dict['JIRA ID'], 'value' : dt_dir})
new_row.cells.append({'column_id': column_dict['Transfer Date'], 'value': mm_dd_yy})
new_row.cells.append({'column_id': column_dict['Data Transfer Expiration'], 'value': exp_date})
new_row.cells.append({'column_id': column_dict['Collaborator Email'], 'value': emails})

response = smart_sheet_client.Sheets.add_rows(data_transfer_sheet.id, new_row)
