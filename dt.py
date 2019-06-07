import sys
import os
import csv
import argparse
import glob

parser = argparse.ArgumentParser()
parser.add_argument('-f', type=str, help='Illumina bam path tsv from imp', required=True)
args = parser.parse_args()

cwd = os.getcwd()

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


def md5_check():
    pass


def gxfr_command(dtdir):

    while True:
        dt_file = dtdir.lower().replace('-', '')
        tag = input('\nEnter data transfer subject line:\n').strip().replace(' ', '\ ')
        emails = input('\nEnter data transfer emails (comma separated list):\n')
        command = 'gxfer-upload-md5 --file={} --tag="{}\ {}" --emails={}'.format(dt_file, tag, dt_dir, emails)

        if 'y' in input('\ngxfer command:\n{}\ny to continue (anything else to re-create):\n'.format(command)).lower():
            with open('gxfer.data.transfer.sh', 'w') as gx:
                gx.write(command)
                print('Data transfer setup complete.')
                break


with open(args.f, 'r') as infiletsv, open('Samplemap.csv', 'w') as sf:

    fh = csv.DictReader(infiletsv, delimiter='\t')
    infile_header = fh.fieldnames
    infile_header.append('Files')

    sm = csv.DictWriter(sf, fieldnames=infile_header, delimiter=',')
    sm.writeheader()

    for line in fh:

        if not os.path.isdir(line['Full Path']):
            print('{} directory not found.'.format(line['Full Path']))
            continue

        paths(line['Full Path'], dt_dir)

        fq_files = glob.glob('{}/*fastq*'.format(line['Full Path']))

        file_field = ''
        for file in fq_files:
            fastq = file.split('/')[-1]
            if 'md5' not in fastq:
                file_field += fastq + ' '

        line['Files'] = file_field.rstrip()

        sm.writerow(line)

gxfr_command(dt_dir)




