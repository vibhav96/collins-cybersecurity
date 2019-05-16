import os
from os.path import join, isdir, abspath, dirname
from waflib import Options, Utils, Logs, TaskGen, Errors
from waflib.Errors import ConfigurationError
from waflib.TaskGen import task_gen, feature, after, before
from waflib.Utils import to_list as listify

def options(opt):
    opt.load('java')
    opt.add_option('--disable-java', action='store_false', dest='java',
                   help='Disable java', default=True)
    opt.add_option('--with-java-home', action='store', dest='java_home',
                   help='Specify the location of the java home')
    opt.add_option('--require-java', action='store_true', dest='force_java',
               help='Require Java (configure option)', default=False)
    opt.add_option('--require-jni', action='store_true', dest='force_jni',
               help='Require Java lib/headers (configure option)', default=False)
    opt.add_option('--require-ant', action='store_true', dest='force_ant',
               help='Require Ant (configure option)', default=False)
    opt.add_option('--with-ant-home', action='store', dest='ant_home',
                    help='Specify the Apache Ant Home - where Ant is installed')    

def configure(self):
    if not Options.options.java:
        return
    
    from build import recursiveGlob
    
    ant_home = Options.options.ant_home or self.environ.get('ANT_HOME', None)
    if ant_home is not None:
        ant_paths = [join(self.environ['ANT_HOME'], 'bin'), self.environ['ANT_HOME']]
    else:
        ant_paths = []

    env = self.env
    env['HAVE_ANT'] = self.find_program('ant', var='ANT', path_list=ant_paths, mandatory=False)

    if not env['ANT'] and  Options.options.force_ant:
        raise Errors.WafError('Cannot find ant!')

    if Options.options.java_home:
        self.environ['JAVA_HOME'] = Options.options.java_home 
    
    try:
        self.load('java')
    except Exception as e:
        if Options.options.force_java:
            raise e
        else:
            return

    if not self.env.CC_NAME and not self.env.CXX_NAME:
        self.fatal('load a compiler first (gcc, g++, ..)')

    try:
        if not self.env.JAVA_HOME:
            self.fatal('set JAVA_HOME in the system environment')
    
        # jni requires the jvm
        javaHome = abspath(self.env['JAVA_HOME'][0])
        
        if not isdir(javaHome):
            self.fatal('could not find JAVA_HOME directory %r (see config.log)' % javaHome)
    
        incDir = abspath(join(javaHome, 'include'))
        if not isdir(incDir):
            self.fatal('could not find include directory in %r (see config.log)' % javaHome)
        
        incDirs = list(set(map(lambda x: dirname(x),
                      recursiveGlob(incDir, ['jni.h', 'jni_md.h']))))
        libDirs = list(set(map(lambda x: dirname(x),
                      recursiveGlob(javaHome, ['*jvm.a', '*jvm.lib']))))
        if not libDirs:
            libDirs = list(set(map(lambda x: dirname(x),
                          recursiveGlob(javaHome, ['*jvm.so', '*jvm.dll']))))
 
        #if not self.check_jni_headers():
        if not self.check(header_name='jni.h', define_name='HAVE_JNI_H', lib='jvm',
                libpath=libDirs, includes=incDirs, uselib_store='JAVA', uselib='JAVA',
                function_name='JNI_GetCreatedJavaVMs'):
            if Options.options.force_jni:
                self.fatal('could not find lib jvm in %r (see config.log)' % libDirs)
    except ConfigurationError as ex:
        err = str(ex).strip()
        if err.startswith('error: '):
            err = err[7:]
        if Options.options.force_java:
            self.fatal(err)
        else:
            self.msg('Java lib/headers', err, color='YELLOW')

# Used to call ant. Assumes the ant script respects a target property.
@task_gen
@feature('ant')
def ant(self):
    if not hasattr(self, 'defines'):
        self.defines = []
    if isinstance(self.defines, str):
        self.defines = [self.defines]
    self.env.ant_defines = map(lambda x: '-D%s' % x, self.defines)
    self.rule = ant_exec

def ant_exec(tsk):
    # Source file is build.xml
    cmd = [tsk.env['ANT'], '-file', tsk.inputs[0].abspath(), '-Dtarget=' + tsk.outputs[0].abspath()] + tsk.env.ant_defines
    return tsk.generator.bld.exec_command(cmd)

def java_module(bld, **modArgs):
    """
    Builds a module, along with optional tests.
    It makes assumptions, but most can be overridden by passing in args.
    """
    if 'env' in modArgs:
        env = modArgs['env']
    else:
        variant = modArgs.get('variant', bld.env['VARIANT'] or 'default')
        env = bld.all_envs[variant]

    if env['JAVAC'] and env['JAR']:
       modArgs = dict((k.lower(), v) for k, v in modArgs.iteritems())
           
       lang = modArgs.get('lang', 'java')
       nlang = modArgs.get('native_lang', 'c')
       libExeType = {'java':'javac'}.get(lang, 'java')
       nsourceExt = {'cxx':'.cpp','c':'.c'}.get(nlang, 'c')
       libName = '%s.jar' % (modArgs['name'])
   		
       path = modArgs.get('path',
                          'dir' in modArgs and bld.path.find_dir(modArgs['dir']) or bld.path)
   
       module_deps = map(lambda x: '%s-%s' % (x, lang), listify(modArgs.get('module_deps', '')))
       uselib_local = module_deps + listify(modArgs.get('uselib_local', '')) + listify(modArgs.get('use',''))
       uselib = listify(modArgs.get('uselib', '')) + ['JAVA']
       targets_to_add = listify(modArgs.get('targets_to_add', ''))
       classpath = listify(modArgs.get('classpath', ''))
       compat = modArgs.get('compat', '1.5')
       libVersion = modArgs.get('version', None)
       installPath = modArgs.get('install_path', None)
       libInstallPath = modArgs.get('lib_install_path', None)
       manifest = modArgs.get('manifest', None)
       jarcreate = modArgs.get('jarcreate', None)
   
       if modArgs.get('nosuffix', False) :
           targetName = modArgs['name']
       else :    
           targetName = '%s-%s' % (modArgs['name'], lang)
           
       sourcedir = modArgs.get('sourcedir', 'src/java')
       native_sourcedir = modArgs.get('native_sourcedir', 'src/jni')
   
       cp_targets = []
       real_classpath = []
       classpathDirs = [bld.path.find_dir('lib'), bld.path.find_dir('libs'), bld.path.find_dir('../libs')]
       for cp in classpath:
           for dir in classpathDirs:
               if dir is not None and os.path.exists(join(dir.abspath(), cp)):
                   real_classpath.append(join(dir.abspath(), cp))
                   cp_targets.append(bld(name=cp, features='install_tgt', install_path=libInstallPath or '${PREFIX}/lib', dir=dir, files=[cp]))
   
       for dep in module_deps:
           tsk = bld.get_tgen_by_name(dep)
           for cp in tsk.classpath:
               real_classpath.append(cp)
   		
       #build the jar
       jar = bld(features='javac jar add_targets install_tgt', manifest=manifest, jarcreate=jarcreate, srcdir=sourcedir, classpath=real_classpath, targets_to_add=targets_to_add + cp_targets, 
   		      use=module_deps, name=targetName, target=targetName, basedir='classes', outdir='classes', destfile=libName, compat=compat, dir=bld.path.get_bld(), files=[libName])
   
       jar.install_path = installPath or '${PREFIX}/lib'
           
   
       if bld.is_defined('HAVE_JNI_H') and bld.path.find_dir(native_sourcedir) is not None:
           lib = bld(features='%s %sshlib' % (nlang, nlang), includes='%s/include' % native_sourcedir,
                                  target='%s.jni-%s' % (modArgs['name'], nlang), env=env.derive(),
                                  uselib=uselib, use=uselib_local,
       						   source=bld.path.find_dir(native_sourcedir).ant_glob('source/*%s' % nsourceExt))
   
           jar.targets_to_add.append(lib)
   		
           lib.install_path = installPath or '${PREFIX}/lib'
   			
       return jar
	
# Tell waf to ignore any build.xml files, the 'ant' feature will take care of them.
TaskGen.extension('build.xml')(Utils.nada)

