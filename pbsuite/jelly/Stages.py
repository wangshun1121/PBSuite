import re
import os
import sys
import glob
import logging
import subprocess
from string import Template

from pbsuite.utils.CommandRunner import Command
from pbsuite.utils.FileHandlers import GapInfoFile

# Change to --debug for use
DEBUG = ""

"""
This code is more about setting up commands to run other things, not actual computations.
"""

PRINT_HELPS = {"setup": os.path.join("Setup.py --help"), \
               "mapping": "blasr -h", \
               "support": os.path.join("Support.py --help"), \
               "extraction": os.path.join("Extraction.py --help"), \
               "assembly": os.path.join("Assembly.py --help"), \
               "output": os.path.join("Collection.py --help")}

def setup(scaffoldName, gapInfoName, extras):
    """
    Generate all the information we need from the input scaffolding
    """
    command = Template("Setup.py ${scaf} -g ${gap} ${debug} ${extras}").substitute( \
        {"scaf":scaffoldName, \
        "gap":gapInfoName, \
        "debug":DEBUG, \
        "extras":extras})
    baseName = os.path.dirname(scaffoldName)
    ret = Command(command, "setup", os.path.join(baseName,"setup.out"), os.path.join(baseName,"setup.err"))
    return ret

def mapping(reads, scaffoldName, blasr_params):
    """
    Please deploy BLASR v5.3+ with Pitchfork
    You will also need SAMtools
    Input:
        - PacBio reads (must be in PacBio BAM format)
        - Flank files from Setup
    Task:
        - Map PacBio reads to flanks
    Output:
        - Indexed BAM files of alignments
    """
#    logFormat = "%(asctime)s [%(levelname)s] %(message)s"
#    level = "DEBUG" if DEBUG != "" else "INFO"
#    logging.basicConfig( stream=sys.stderr, level=level, format=logFormat )
#    logging.info("Running blasr")

    # Run the BLASR mapping jobs
    basename = '.'.join(scaffoldName.split('.')[:-1])
    endsL = {"reads": reads, "flanks": basename+'_ends.L.fa', "out": basename+"_ends.L.bam", "param": blasr_params}
    endsR = {"reads": reads, "flanks": basename+'_ends.R.fa', "out": basename+"_ends.R.bam", "param": blasr_params}
    gapsL = {"reads": reads, "flanks": basename+'_gaps.L.fa', "out": basename+"_gaps.L.bam", "param": blasr_params}
    gapsR = {"reads": reads, "flanks": basename+'_gaps.R.fa', "out": basename+"_gaps.R.bam", "param": blasr_params}
    mappingTemplate = Template("blasr ${reads} ${flanks} --bam --out ${out} --hitPolicy allbest ${param}")
    mappingJobs = [endsL, endsR, gapsL, gapsR]
    for job in mappingJobs:
        subprocess.call(mappingTemplate.substitute(job).split(' '))
    # Index the BAM alignment files
    endsL = {"aligns": basename+"_ends.L.bam"}
    endsR = {"aligns": basename+"_ends.R.bam"}
    gapsL = {"aligns": basename+"_gaps.L.bam"}
    gapsR = {"aligns": basename+"_gaps.R.bam"}
    indexingTemplate = Template("samtools index ${aligns}")
    indexingJobs = [endsL, endsR, gapsL, gapsR]
    for job in indexingJobs:
        subprocess.call(indexingTemplate.substitute(job).split(' '))

#   tailTemplate = Template("m4pie.py ${outFile} ${fasta} ${ref} --nproc ${nproc} -i ${extras}")
    
#    ret = []
#    #sa safety
#    if os.path.exists(referenceSa):
#        referenceSa = "--sa " + referenceSa
#    else:
#        logging.critical("Specified reference.sa %s does not exists. Mapping will be slower" % (referenceSa))
#        referenceSa = ""
    
#    for fasta in jobDirs:
#        name = fasta[fasta.rindex('/')+1:]
#        
#        if not os.path.exists(fasta):
#            logging.error("%s doesn't exist." % fasta)
#            exit(1)
#        
#        outFile = os.path.join(outDir,name+".m4")
#        if os.path.isfile(outFile):
#            logging.warning("Output File %s already exists and will be overwritten." % (outFile))
#        
#        #Build Blasr Command 
#        nprocRe = re.compile("-nproc (\d+)")
#        np = nprocRe.findall(parameters + extras)
#        if len(np) == 0:
#            np = '1'
#        else:
#            np = np[-1]
#
#
#        cmd2= tailTemplate.substitute( {"fasta":fasta,
#                           "ref":reference,
#                           "outFile":outFile,
#                           "nproc": np,
#                           "extras":extras} )
#        fullCmd = cmd + "\n" + cmd2
#        #Build Command to send to CommandRunner 
#        jobname = name+".mapping"
#        stdout = os.path.join(outDir, name+".out")
#        stderr = os.path.join(outDir, name+".err")
#        ret.append( Command(fullCmd, jobname, stdout, stderr) )
#    
#    return ret


def support(inputDir, gapTable, outputDir, extras):
    ret = []
    command = Template("Support.py ${inputm4} ${gapTable} ${outFile} ${debug} ${extras}")
    mappingFiles = glob.glob(os.path.join(inputDir, "mapping/*.m4"))
    
    if len(mappingFiles) == 0:
        logging.warning("No mapping files found!")
        return ret
    
    for inputm4 in  mappingFiles:
        baseName = inputm4[inputm4.rindex('/')+1:inputm4.rindex(".m4")]
        outFile = os.path.join(outputDir, baseName+".gml")
        if os.path.isfile(outFile):
            logging.warning("Overwriting %s" % outFile)
        myCommand = command.substitute( {"inputm4": inputm4,\
                         "gapTable": gapTable,\
                         "outFile": outFile,\
                         "debug": DEBUG,\
                         "extras":extras} )
        
        ret.append( Command(myCommand,\
                     baseName+".support",\
                     os.path.join(outputDir,baseName+".out"),\
                                 os.path.join(outputDir,baseName+".err")) )

    return ret

def extraction(outputDir, protocol, extras):
    command = Template("Extraction.py ${protocol} ${debug} ${extras}")
    myCommand = command.substitute({"protocol": protocol, \
                    "debug":DEBUG, \
                    "extras":extras})
    
    return Command(myCommand, "extraction", \
                os.path.join(outputDir,"extraction.out"), \
                os.path.join(outputDir,"extraction.err"))

def assembly(inputDir, gapInfoFn, extras):
        
    gapInfo = GapInfoFile(gapInfoFn)
    command = Template("Assembly.py ${inputDir} ${size} ${debug} ${extras}")
    ret = []
    allInputs = glob.glob(os.path.join(inputDir,"ref*"))
    if len(allInputs) == 0:
        logging.warning("No gaps to be assembled were found in %s! Have you run 'extraction' yet?" % inputDir)
        sys.exit(1)
        
    for inputDir in allInputs:
        #get The predicted size if exists
        mySize = ""
        gapName = inputDir.split('/')[-1]
        if gapName.count('.') > 0:
            g = gapName.split('_')
            if len(g) == 1:
                ref,cnam = g[0].split('.')
                cn = int(cnam[:-2])
                if cnam.endswith('e5'):
                    ca = cn-1
                    cb = cn
                elif cnam.endswith('e3'):
                    ca = cn
                    cb = cn+1
                else:
                    logging.error("Single End Extension is misFormatted for %s" % inputDir)
                    exit(1)
                size = gapInfo["%s_%d_%d" % (ref, ca, cb)].length
                mySize = "-p %d" % (size)
            elif len(g) == 2:
                ref,ca = g[0].split('.')
                ref,cb = g[1].split('.')
                #Hackey Shack. - effect of sorting node names to prevent redundancies during graph building
                ca = int(ca[:-2])
                cb = int(cb[:-2])
                j = [ca,cb]
                j.sort()
                ca, cb = j
                size = gapInfo["%s_%d_%d" % (ref, ca, cb)].length
                mySize = "-p %d" % (size)
            else:
                logging.error("Couldn't recreate gapName from refDir for %s" % inputDir)
                exit(1)
        myCommand = command.substitute({"inputDir":inputDir,\
                                        "size":mySize,\
                                        "debug":DEBUG,\
                                        "extras":extras})
        
        ret.append(Command(myCommand, 
               os.path.join(inputDir.split('/')[-1],"assembly"), \
               os.path.join(inputDir,"assembly.out"), \
               os.path.join(inputDir,"assembly.err")) )
    
    return ret


def collection(inputDir, protocol, extras):
    command = Template("Collection.py ${protocol} ${extras}")
    
    myCommand = command.substitute({"protocol": protocol.protocolName,
                                    "extras": extras})
    
    return Command(myCommand, \
            os.path.join(inputDir,"collectingOutput"), \
            os.path.join(inputDir,"output.out"), \
            os.path.join(inputDir,"output.err"))

