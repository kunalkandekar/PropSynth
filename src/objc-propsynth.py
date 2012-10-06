#!/user/bin/python

import fileinput, glob, string, sys, os, re
import shutil

property_map = {}
class_list  = set()
updated_h_files = set()
orig_synth_file_map = dict()
synthed_files_to_keep = set()
synth_prefix = './synth_files/'
synth_suffix = '' #'_synth'
delete_unchanged_files = False
backup_orig_files = True
backup_orig_files_prefix = './original/'
write_synth = True
synth_in_place = True

class Property(object):
    def __init__(self):
        self.prop_id   = ''
        self.impl_name = ''
        self.prop_name = ''
        self.prop_type = ''
        self.attrs = []
        self.is_pointer  = False
        self.attr_read   = False
        self.attr_write  = False
        self.attr_assign = False
        self.attr_retain = False
        self.attr_copy   = False
        self.attr_atomic = False    #not well handled currently
        self.setter = ''
        self.getter = ''
        self.setter_def = ''
        self.getter_def = ''

    def set_type(self, typename):
        self.prop_type = typename.strip()
        if self.prop_type[-1:] == '*':
            self.is_pointer = True

    def parameterize(self, val):
        return '_'+val #'in'+val[0:1].upper()+val[1:]

    def generate_setter(self):
        if not self.attr_write:
            return
        prop_param = self.parameterize(self.prop_name)
        self.setter = '\n- (void) set'+self.prop_name[0:1].upper() + self.prop_name[1:]
        self.setter += ':('+self.prop_type+') '+prop_param
        self.setter += '  // auto-generated setter' #comment
        self.setter += '\n{'
        if self.is_pointer:
            self.setter += '\n\tif (self->'+self.prop_name+' != '+prop_param+')'
            self.setter += '\n\t{'
            if self.attr_retain:
                self.setter+=  '\n\t\tself->'+self.prop_name + ' = ' + prop_param+';'
                self.setter += '\n\t\t[self->'+self.prop_name+ ' retain];'
            elif self.attr_assign:
                self.setter += '\n\t\t[self->'+self.prop_name+ ' release];'
                self.setter += '\n\t\tself->'+self.prop_name+ ' = ['+ prop_param+' retain];';
            else: #copy
                self.setter += '\n\t\t[self->'+self.prop_name+ ' release];'
                self.setter += '\n\t\tself->'+self.prop_name+ ' = ['+ prop_param+' copy];';
            self.setter += '\n\t}'
        else:
            self.setter +=  '\n\tself->'+self.prop_name + ' = ' + prop_param+';'
        self.setter += '\n}\n\n'
        
    def generate_getter(self):
        if not self.attr_read:
            return
        self.getter  = '\n- ('+self.prop_type+') ' + self.prop_name
        self.getter += '  // auto-generated getter' #comment
        self.getter += '\n{'
        self.getter += '\n\treturn self->'+self.prop_name+';'
        self.getter += '\n}\n\n'
        
    def generate_methods(self):
        self.generate_setter()
        self.generate_getter()

    def generate_setter_def(self):
        if not self.attr_write:
            return
        prop_param = self.parameterize(self.prop_name)
        self.setter_def = '\n- (void) set'+self.prop_name[0:1].upper() + self.prop_name[1:]
        self.setter_def += ':('+self.prop_type+') '+prop_param+';'
        self.setter_def += '  // auto-generated setter' #comment
        self.setter_def += '\n\n'
        
    def generate_getter_def(self):
        if not self.attr_read:
            return
        self.getter_def  = '\n- ('+self.prop_type+') ' + self.prop_name+';'
        self.getter_def += '  // auto-generated getter' #comment
        self.getter_def += '\n\n'
       
    def generate_definitions(self):
        self.generate_setter_def()
        self.generate_getter_def()

    def to_s(self):
        return self.prop_id+':('+', '.join(self.attrs) +'):('+self.prop_type+'):'+self.prop_name

#end class property

def split_regex(regex, string): #return non-empty strings only
    return [w for w in re.split(regex, string) if (w != '')] 

def write_thru(outfile, line, comment_out=False):
    if not outfile: return
    if comment_out:
        outfile.write('//'+line)
    else:
        outfile.write(line)

def get_synth_filename(fname):
    outfilename = get_no_dotpath_filename(fname)
    if fname[-2:] == '.h':
        outfilename = synth_prefix + fname[:-2]+synth_suffix+'.h'
    elif fname[-2:] == '.m':
        outfilename =  synth_prefix + fname[:-2]+synth_suffix+'.m'
    elif fname[-3:] == '.mm':
        outfilename =  synth_prefix + fname[:-3]+synth_suffix+'.mm'
    return outfilename

def get_backup_filename(fname):
    bakfilename = get_no_dotpath_filename(fname)
    bakfilename = backup_orig_files_prefix + bakfilename
    bakdirname  = get_backup_dirname(fname)
    return bakfilename

def get_backup_dirname(fname):
    bakfilename = get_no_dotpath_filename(fname)
    bakfilename = backup_orig_files_prefix + bakfilename
    bakdirname  = os.path.dirname(bakfilename)
    if not os.path.exists(bakdirname):
        os.makedirs(bakdirname)
    return bakdirname

def get_no_dotpath_filename(fname):
    if fname[0:2] =='./': return fname[2:]    
    return fname

def find_properties(fname, write_to_file=True):
    if not os.path.exists(fname) or not os.path.isfile(fname): return
    outfilename = None
    outfile     = None
    if write_to_file:
        outfilename = get_synth_filename(fname)
        outdirname = os.path.dirname(outfilename)
        if not os.path.exists(outdirname):
            os.makedirs(outdirname	)
        outfile = open(outfilename, 'w')
    
    last_class_name = ''
    print 'parsing file ', fname
    lineno = 0
    
    b_properties_found = False
    
    for line in fileinput.input(fname):
        lineno += 1
        #check for comments
        comment_index = line.find('//')
        index = line.find('@interface')
        
        property_found = False
        
        if (index >= 0) and ((comment_index < 0) or (index < comment_index)):
            #get name of interface
            tokens = split_regex('[\s]+', line)
            l = len(tokens)
            for i in range(l):
                if tokens[i] == '@interface' and (i < (l - 1)):
                    last_class_name = tokens[i + 1]
                    if (last_class_name[-1:] == ':'): #strip trailing colon if any
                        last_class_name = last_class_name[:-1]
                    #print lineno, ':begin interface:',last_class_name
            #end  for i in range
        #end line.find

        index = line.find('@end')
        if (index >= 0) and ((comment_index < 0) or (index < comment_index)): #wipe out impl name if any
            #print lineno, ':end interface:', last_class_name
            last_class_name = ''

        index = line.find('@property')
        if (index >= 0) and ((comment_index < 0) or (index < comment_index)): #work on property if we find one
            #save this file as an import file that we modified
            fname_nopath = get_no_dotpath_filename(fname)
            updated_h_files.add(fname_nopath)
            #synthed_files_to_keep.add(fname)

            index_attr_s = line[index:].find('(')
            index_attr_e = line[index:].find(')')
            next_index = index_attr_e + 1
            prop = Property()
            b_properties_found = True
            if (index_attr_s >= 0) and (index_attr_e > index_attr_s):
                attr_clause = line[index_attr_s+1:index_attr_e]
                tokens = split_regex('[\s,]+', attr_clause)
                l = len(tokens)
                for i in range(l):
                    prop.attrs.append(tokens[i])
                    if (tokens[i] == 'readwrite'):
                        prop.attr_read  = True
                        prop.attr_write = True
                    elif (tokens[i] == 'readonly'):
                        prop.attr_read  = True
                        prop.attr_write = False
                    elif (tokens[i] == 'writeonly'):
                        prop.attr_read  = False
                        prop.attr_write = True
                    else:
                        prop.attr_read  = True
                        prop.attr_write = True
                    if (tokens[i] == 'assign'):
                        prop.attr_assign = True
                    if (tokens[i] == 'retain'):
                        prop.attr_retain = True
                    if (tokens[i] == 'atomic'):
                        prop.attr_atomic = True
                    if (tokens[i] == 'nonatomic'):
                        prop.attr_atomic = False
            else: #not found
                next_index = index + 1
            remaining_line = line[next_index:]
            remaining = split_regex('[\s]+', remaining_line)
            
            if len(remaining) > 1:
                prop_type = remaining[0]
                if len(remaining) > 2:
                    if remaining[-2] == '*': # pointer
                        prop_type += ' *'
                        prop.prop_name = remaining[-1]
                    if remaining[0] == 'unsigned': # unsigned type
                        prop_type = 'unsigned '+ remaining[1]
                        prop.prop_name = remaining[-1]
                    else:
                        print lineno, ':more tokens than expected ['+','.join(remaining)+']'
                        continue #unexpected case
                else:
                    if remaining[1][0] == '*':  #pointer
                            prop_type += ' *'
                            prop.prop_name = remaining[1][1:]
                    else:
                        prop.prop_name = remaining[1]
                
                prop.set_type(prop_type)
                
                if prop.prop_name[-1:] == ';':
                    prop.prop_name = prop.prop_name[0:-1]                    
                prop.prop_id = last_class_name+'.'+prop.prop_name
                #done prop line

                property_map[prop.prop_id] = prop
                property_found = True
                #print 'added prop: ', prop.to_s()
            #else  either type or property name missing
            
        write_thru(outfile, line, property_found) #write through to synthesized file
        if property_found:    #write the replaced definitions
            prop.generate_definitions();
            print 'prop: ', prop.to_s(), prop.setter_def, prop.getter_def
            write_thru(outfile, prop.setter_def)
            write_thru(outfile, prop.getter_def)
    #end for
        
    if outfile:
        outfile.close()
        #delete temp file if we didn't change anything
        if b_properties_found:
            print 'keeping synth file', outfilename
            updated_h_files.add(get_no_dotpath_filename(outfilename))
            synthed_files_to_keep.add(outfilename)
            orig_synth_file_map[fname] = outfilename
        elif delete_unchanged_files:
            print 'deleting synth file', outfilename
            os.remove(outfilename)
    #done

def synth_properties(filename, write_to_file=True):
    fname = filename
    orig_fname = fname
    if not os.path.exists(fname) or not os.path.isfile(fname): return
    print 'parsing file ', fname
    outfilename = None
    outfile     = None
    b_tmp_file  = False
    if write_to_file:
        outfilename = get_synth_filename(fname)
        if os.path.exists(outfilename): #already synthesized, so parse the synthesized file instead 
            #rename synthesized file to temp file so new synth file does not overwrite it
            fname = outfilename+'.tmp'
            print 'parsing synthesized file',outfilename, 'renaming to',fname
            os.rename(outfilename, fname)
            b_tmp_file = True
        outfile = open(outfilename, 'w')
    last_class_name = ''
    lineno = 0
    b_file_changed = False
    
    for line in fileinput.input(fname):
        lineno += 1
        property_found = False

        #check for comments
        comment_index = line.find('//')
                
        #check for implementation
        index = line.find('@implementation')
        if (index >= 0) and ((comment_index < 0) or (index < comment_index)):
            #get name of interface
            tokens = split_regex('[\s]+', line)
            l = len(tokens)
            for i in range(l):
                if tokens[i] == '@implementation' and (i < (l - 1)):
                    last_class_name = tokens[i + 1]
                    if (last_class_name[-1:] == ':'): #strip trailing colon if any
                        last_class_name = last_class_name[:-1]

                        #keep track of this class for later purposes
                        class_list.add(last_class_name)
                    #print lineno, ':begin implementation:',last_class_name
            #end  for i in range
        #end line.find

        index = line.find('@end')
        if (index >= 0) and ((comment_index < 0) or (index < comment_index)): #wipe out impl name if any
            #print lineno, ':end interface:', last_class_name
            last_class_name = ''

        index = line.find('@synthesize')
        if (index >= 0) and ((comment_index < 0) or (index < comment_index)): #work on property
            remaining_line = line[index+len('@synthesize'):]
            tokens = split_regex('[\s]+', remaining_line)
            prop_name = tokens[-1]
            if prop_name[-1:] == ';': prop_name = prop_name[0:-1]
            #find prop
            prop_id = last_class_name + '.' + prop_name
            try:
                prop = property_map[prop_id]
            except KeyError:
                print prop_id, ' not found in property_map'
                continue 
            print lineno, ' synthesizing ', prop_id
            print 'prop: ', prop.to_s(), prop.setter, prop.getter
            #replace in file
            
            #now remove from dict
            del property_map[prop_id]
            
            b_properties_found = True
            b_file_changed = True
            
            write_thru(outfile, line, True)     #comment and write through to synthesized file
            write_thru(outfile, prop.setter)    #write setter to synthesized file
            write_thru(outfile, prop.getter)    #write getter to synthesized file            
        else:   #else @impl not found, just write through
            write_thru(outfile, line) #write through to synthesized file
    #end for
    
    if outfile:
        outfile.close()
        if b_file_changed:
            synthed_files_to_keep.add(outfilename)
            orig_synth_file_map[orig_fname] = outfilename
        else:
            #delete output file if we didn't change anything
            if delete_unchanged_files: #b_properties_found:
                os.remove(outfilename)
    #delete parsed file if it was a temp file
    if b_tmp_file:
        print 'deleting tmp file', fname
        os.remove(fname)
    #done

def move_files(in_place=False):
    if in_place:
        for orig_fname, synth_fname in orig_synth_file_map.iteritems():
            #backup by default if expanding in place
            bakfilename = get_backup_filename(orig_fname)
            print 'backing up ',orig_fname,' to ',bakfilename
            shutil.copy2(orig_fname, bakfilename)
            print 'replacing ',orig_fname,' with ', synth_fname 
            shutil.copy2(synth_fname, orig_fname)
        #end for
    #end if

def generate_methods():
    for prop_name, prop in property_map.items():
        #generate methods
        prop.generate_methods()

def is_ojbc_source_file(f):
    return (f.find('.svn') < 0) and ((f[-3:] == '.mm') or (f[-2:] == '.m')) #and !f.endswith('_synth.m') and !f.endswith('_synth.mm')
    
def is_ojbc_header_file(f):
    return (f.find('.svn') < 0) and (f[-2:] == '.h') #and !f.endswith('_synth.m') and !f.endswith('_synth.mm')

def run():
    #files = os.listdir('.')
    src_files  = []
    hdr_files  = []
    b_expore_recursive = False

    if b_expore_recursive:
        for root, dirs, files in os.walk('.'):
            if root.find('.svn') >= 0 or root.find('./build') == 0: continue
            hdr_files.extend([os.path.join(root, f)  for f in files if is_ojbc_header_file(f)])
            src_files.extend([os.path.join(root, f)  for f in files if is_ojbc_source_file(f)])
    else:
        root = '.'
        files = os.listdir('.')
        #if file.find('.svn') >= 0 or file.find('./build') == 0: continue
        hdr_files.extend([os.path.join(root, f)  for f in files if is_ojbc_header_file(f)])
        src_files.extend([os.path.join(root, f)  for f in files if is_ojbc_source_file(f)])

    for filename in hdr_files:
        find_properties(filename, write_synth)

    for filename in src_files:
        find_properties(filename, write_synth)   #look for properties in source files as well

    generate_methods()

    for filename in src_files:        
        synth_properties(filename, write_synth)
    
    move_files(synth_in_place)

    print '# un-synthesized properties =', len(property_map)
    #print str(property_map)

run()
