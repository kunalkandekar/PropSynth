                        PropSynth for Objective-C
                        -------------------------

                          Kunal Kandekar 
                       kunalkandekar@gmail.com

This script recursively scans through all Objective-C 2.0 .h and .mm files in a 
given directory, identifes all the properties declared, and "synthesizes" getter
and setter (or accessors/mutator or what-have-you) methods for those properties
in the corresponding @implementation blocks. This script does not modify the 
original files, and instead generates parallel files with a given filename 
prefix to differentiate the synthesized files.

Wait, wasn't the whole point of @property and @synthesize directives that you 
would NOT need to do this? Why is this needed then, you may ask. Because until 
recently, GNUstep (Objective-C / NeXtStep on Linux) could only handle 
Objective-C 1.0, where as properties and the @synthesize were something from
Objective-C 2.0. Hence GNUstep (until recently) could not parse with @synthesize
directives and choked. 

Relevant StackOverflow question:
http://stackoverflow.com/questions/1250658/will-gnustep-support-property-and-synthesize

Heck, I haven't looked at it since 2009, so I still don't know if this problem 
is solved, but certain links seem to indicate so:
http://wiki.gnustep.org/index.php/ObjC2_FAQ

However, it seems that they target clang, and Objective-C 2.0 features still 
don't work with GCC. So anybody who wishes to compile Obj-C 2.0 code with GCC is
still in for some pain, some of which this script may alleviate.

I ran into this in 2009 when porting an application from OS X to Linux. Why did 
I do that? The answer when I started out was "just for kicks," but the real 
answer by the time I got done was "Because I'm a masochist, that's why." I also 
ran into bugs in the RegexKit port on GNUstep, for which I filed bug reports AND
patches that still haven't been looked at :-(

Anyway, I'm just putting this script out there in case anybody finds it useful.
Like people having to compile Objective-C 2.0 code on GNUstep with GCC.

OVERVIEW
Basic operation is very simple:
1. Pass 1, "find_properties" - For each detected .h or .mm file:
    a) identify class declarations as code between lines containing "@interface"
       and "@end"
        (i) detect class name as the token that comes after @interface
    b) identify properties as code that starts with "@property"
        (i) detect any attributes (assign, retain, atomic etc.)
       (ii) detect property type and name as the tokens that comes after 
            @property and optional attributes
    c) Associate the detected type, name and attributes of properties as members
       of the detected class.
2. Pass 2, "synth_properties" - For each detected .mm file:
    a) identify class implementations as code between lines containing 
       "@implementation" and "@end"
       (i) detect class name as the token that comes after @implementation
      (ii) bring up the relevant class/property associations from 1.c)
    b) identify synthesize directives as code that starts with "@synthesize"
       (i) detect property name as the token that comes after @synthesize
      (ii) identify the property name, type and attributes from 2.a(ii)
    c) Generate a basic setter/getter method based on the property type and 
       attributes.
    d) Duplicate all other code surrounding the @synthesize statements in the
       appropriate order.
    e) Write it all out into a new file with filename = prefix + input filename


CAVEAT DEVELOPER!
This script does VERY VERY basic parsing of the text to identify @property and 
their corresponding @synthesize directives. Thus, trivial variations on the 
structure of the code it expects could break it. Here are a few stumbling blocks
I could think of off the top of my head:
* Not having the "@property" statement and the corresponding property-name and
  attributes on the same line;
* Not having the "@synthesize" directive and the corresponding property-name on 
  the same line;
* Ditto for "@interface" and class name, or "@implementation" and class name.
* Ignoring any code between multi-line /* … */ comments.
* Detecting the presence of specific setter or getter implementations you 
  provide yourselves. (You will end up with a duplicate generic setter/getter.)
* Any unexpected syntactic or semantic errors in your own code.

I tested it with only a couple of relatively-small, internal projects. As such 
there may be many, many bugs that I have not encountered, let alone fixed.
