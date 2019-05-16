import sys, os, types, re, fnmatch, subprocess, shutil, platform, inspect
from os.path import split, isdir, isfile, exists, splitext, abspath, join, \
                    basename, dirname

from waflib import Options, Utils, Logs, TaskGen
from waflib.Configure import conf, ConfigurationContext
from waflib.Build import BuildContext, ListContext, CleanContext, InstallContext
from waflib.TaskGen import task_gen, feature, after, before
from waflib.Utils import to_list as listify
from waflib.Tools import waf_unit_test
from waflib import Context, Errors

COMMON_EXCLUDES = '.bzr .bzrignore .git .gitignore .svn CVS .cvsignore .arch-ids {arch} SCCS BitKeeper .hg _MTN _darcs Makefile Makefile.in config.log'.split()
COMMON_EXCLUDES_EXT ='~ .rej .orig .pyc .pyo .bak .tar.bz2 tar.gz .zip .swp'.split()

# provide a partial function if we don't have one
try:
    from functools import partial
except:
    def partial(fn, *cargs, **ckwargs):
        def call_fn(*fargs, **fkwargs):
            d = ckwargs.copy()
            d.update(fkwargs)
            return fn(*(cargs + fargs), **d)
        return call_fn
        
class CPPContext(Context.Context):
    """
    Create a custom context for building C/C++ modules/plugins
    """
    cmd='evil'
    module_hooks = []
    
    def safeVersion(self, version):
        return re.sub(r'[^\w]', '.', version)
    
    def __getDefines(self, env):
        defines = []
        for line in env.DEFINES:
            split = line.split('=')
            k = split[0]
            v = len(split) == 2 and split[1] or '1'
            if v is not None and v != ():
                if k.startswith('HAVE_') or k.startswith('USE_'):
                    defines.append(k)
                else:
                    defines.append('%s=%s' % (k, v))
        return defines

    def pprint(self, *strs, **kw):
        colors = listify(kw.get('colors', 'blue'))
        colors = map(str.upper, colors)
        for i, s in enumerate(strs):
            sys.stderr.write("%s%s " % (Logs.colors(colors[i % len(colors)]), s))
        sys.stderr.write("%s%s" % (Logs.colors.NORMAL, os.linesep))

        
#    # recursively expand packages
#    def __extendPackages(self, env, pkgs, iter) :
#
#        packages = pkgs
#        
#        if iter == len(packages) :
#            return packages
#
#        if packages[iter].isupper() :
#            p = 'PACKAGE_' + packages[iter]
#            packages.remove(packages[iter])
#            if p in env :
#                packages.extend(env[p])
#            packages = self.__extendPackages(env, packages, iter)
#        else :
#            packages = self.__extendPackages(env, packages, iter+1)
#            
#        return packages                 

#    # expand package definitions into targets    
#    def extendPackages(self, env, pkgs) :
#        return self.__extendPackages(env, pkgs, 0)

                    
#    # updates the targets based on packages defined
#    def addPackageList(self, packages, env) :
#        targets = Options.options.compile_targets.split(',')
#        pkgsTargets = self.extendPackages(env, packages)
#        targets.extend(pkgsTargets)
#        
#        # remove duplicates
#        targets = self.removeDuplicates(targets)
#        Options.options.compile_targets = ','.join(targets)

        
    # because we can't assume python 2.6
    def __computeRelPath(self, rel, frm) :
    
        rel = abspath(rel)
        frm = abspath(frm)

        relList = rel.split(os.sep)
        fromList = frm.split(os.sep)

        for folder in fromList :
            if len(relList) > 0 and relList[0] == folder :
                relList.remove(folder)
        return join(*relList)
        
    # find what should be excluded
    def __dontDist (self, name, src, pkgExcludes, build_dir):

        # if initialized to the list, it was residually appending 
        # multiple version, so we start with an empty list
        excludes = []
        dist_exts = []
        excludes.extend(COMMON_EXCLUDES)
        dist_exts.extend(COMMON_EXCLUDES_EXT)

        for ex in pkgExcludes :
            excludes.append(join(str(self.path), ex))
        dist_exts.extend(pkgExcludes)
        
        if (name.startswith(',,') or name.startswith('++') or name.startswith('.waf-1.') or \
           (src=='.' and name == Options.lockfile) or name in excludes or name == build_dir or \
            join(src, name) in excludes or name == "" and src in excludes):
            return True
        for ext in dist_exts :
            if name.endswith(ext) :
                return True

        return False

    # copy the entire directory minus certain things excluded --
    # this takes walking over individual elements     
    def copyTree(self, src, dst, pkgExcludes, build_dir):

        if self.__dontDist("", src, pkgExcludes, build_dir):
            return
        
        names = os.listdir(src)
        if not exists(dst) :
            os.makedirs(dst)

        for name in names:
            srcname = join(src, name)
            dstname = join(dst, name)

            # build_dir is just to safeguard the dest being in the checkout area
            if self.__dontDist(name, src, pkgExcludes, build_dir):
                continue
            if isdir(srcname):
                self.copyTree(srcname, dstname, pkgExcludes, build_dir)
            else:
                shutil.copy2(srcname, dstname)

    def removeDuplicates(self, lst) :
        # remove duplicates
        if lst :
            lst.sort()
            last = lst[-1]
            for i in range(len(lst)-2, -1, -1):
                if lst[i] == '' or last == lst[i] :
                    del lst[i]
                else:
                    last = lst[i]
        return lst
        
    # copies source to the output location
    def __makeSourceDelivery(self, dirs) :

        variant = self.env['VARIANT'] or 'default'
        env = self.all_envs[variant]

        wafDir = abspath('./')
        if isinstance(dirs, str):
            dirs = dirs.split()
        for dir in dirs :
            if dir is None :
                continue

            dir = join(self.path.abspath(), dir)
            relPath = self.__computeRelPath(dir, wafDir)

            # find things in env
            deliverSource = env['DELIVER_SOURCE']
            prefix = env['PREFIX']

            # parse package excludes
            pkgs = []
            if Options.options.packages :
                pkgs = Options.options.packages.split(',')
            pkgsExcludes = []
            for pkg in pkgs :
                pkg = pkg.upper()
                pkg = pkg.strip()
                if pkg in env['BUILD_PACKAGES'] :
                    pkgsExcludes.extend(env['BUILD_PACKAGES'][pkg]['SOURCE_EXCLUDES'])

            pkgsExcludes = self.removeDuplicates(pkgsExcludes)
            
            if self.is_install and exists(dir) and deliverSource is True : 
                relPath = self.__computeRelPath(dir, wafDir)

                # convert relative excluded paths to full paths
                parsedExcludes = []
                for pkgEx in pkgsExcludes:
                    dir = abspath(join(wafDir, pkgEx))
                    if exists(dir) :
                        parsedExcludes.append(dir)
                    else :
                        parsedExcludes.append(pkgEx)

                # deliver all source from relPath recursively
                self.copyTree(join(wafDir, relPath), 
                              join (prefix, 'source', relPath), 
                              parsedExcludes, prefix)


    # wrapper function for delivering everything below a wscript pickup
    def __add_subdirs_withSource(self, dirs) :
    
        if dirs is None :
            return
        if isinstance(dirs, str):
            dirs = dirs.split()
        for dir in dirs :
            if dir is None :
                continue
                
            self.__makeSourceDelivery(dir)
            if not exists(join(self.path.abspath(), dir, 'wscript')) :
                self.fromConfig(dir)
            else :
                self.recurse(dir)
        
    # wrapper function for delivering everything below a project.cfg pickup
    def __fromConfig_withSource(self, dirs, **overrides) :
    
        if dirs is None :
            return
        self.__makeSourceDelivery(dirs)
        self.fromConfig(dirs, **overrides)
        
        
        
        
    def fromConfig(self, path, **overrides):
        bld = self
        from ConfigParser import SafeConfigParser as Parser
        cp = Parser()
        
        if (type(path) != str):
            path = path.abspath()
        
        if isdir(path):
            for f in 'project.cfg module.cfg project.ini module.ini'.split():
                configFile = join(path, f)
                if isfile(configFile):
                    cp.read(configFile)
                    path = configFile
                    break
        elif isfile(path):
            cp.read(path)
        
        sectionDict = lambda x: dict(cp.items(filter(lambda x: cp.has_section(x), [x, x.lower(), x.upper()])[0]))
        
        args = sectionDict('module')
        args.update(overrides)
        
        if 'path' not in args:
            if 'dir' in args:
                args['path'] = bld.path.find_dir(args.pop('dir'))
            else:
                pardir = abspath(dirname(path))
                curdir = bld.path.abspath()
                if pardir.startswith(curdir):
                    relDir = './%s' % pardir[len(curdir):].lstrip(os.sep)
                    args['path'] = bld.path.find_dir(relDir)
                else:
                    args['path'] = bld.path
        
        #get the env
        if 'env' in args:
            env = args['env']
        else:
            variant = args.get('variant', bld.env['VARIANT'] or 'default')
            env = bld.all_envs[variant]
        
        # do some special processing for the module
        excludes = args.pop('exclude', None)
        if excludes is not None:
            if type(excludes) == str:
                args['source_filter'] = partial(lambda x, t: basename(str(t)) not in x,
                                                excludes.split())
        elif 'source' in args:
            source = args.pop('source', None)
            if type(source) == str:
                args['source_filter'] = partial(lambda x, t: basename(t) in x,
                                                source.split())

        try:
            testArgs = sectionDict('tests')
            excludes = testArgs.pop('exclude', None)
            if excludes is not None:
                if type(excludes) == str:
                    args['test_filter'] = partial(lambda x, t: basename(t) not in x,
                                                excludes.split())
            elif 'source' in testArgs:
                source = testArgs.pop('source', None)
                if type(source) == str:
                    args['test_filter'] = partial(lambda x, t: basename(t) in x,
                                                source.split())
        except Exception:{}
        
        try:
            testArgs = sectionDict('unittests')
            excludes = testArgs.pop('exclude', None)
            if excludes is not None:
                if type(excludes) == str:
                    args['unittest_filter'] = partial(lambda x, t: basename(t) not in x,
                                                excludes.split())
            elif 'source' in testArgs:
                source = testArgs.pop('source', None)
                if type(source) == str:
                    args['unittest_filter'] = partial(lambda x, t: basename(t) in x,
                                                source.split())
        except Exception:{}
        
        self.module(**args)
        
        try:
            progArgs = sectionDict('programs')
            files = progArgs.pop('files', '')
            for f in files.split():
                parts = f.split('|', 2)
                self.program_helper(module_deps=args['name'], source=parts[0],
                             path=args['path'],
                             name=basename(splitext(len(parts) == 2 and parts[1] or parts[0])[0]))

        except Exception:{}
    
    def build_packages(self, packages) :

        variant = self.env['VARIANT'] or 'default'
        env = self.all_envs[variant]

        if isinstance(packages, str):
            packages = packages.split(',')
            
        # parse packages        
        pkgsDirs = []
        pkgsTargets = []
        pkgsIncludes = []
        pkgsExcludes = []
        for package in packages :
            if package is None :
                continue
            package = package.upper()
            package = package.strip()

            pkgsDirs.extend(env['BUILD_PACKAGES'][package]['SUB_DIRS'])
            pkgsTargets.extend(env['BUILD_PACKAGES'][package]['TARGETS'])
            pkgsIncludes.extend(env['BUILD_PACKAGES'][package]['SOURCE_INCLUDES'])
            pkgsExcludes.extend(env['BUILD_PACKAGES'][package]['SOURCE_EXCLUDES'])
            
        # make sure there weren't repeats between packages
#        pkgsDirs = self.removeDuplicates(pkgsDirs) # this depends on order
        pkgsTargets = self.removeDuplicates(pkgsTargets)
        pkgsIncludes = self.removeDuplicates(pkgsIncludes)
        pkgsExcludes = self.removeDuplicates(pkgsExcludes)
        
        # add sub_dirs
        self.__add_subdirs_withSource(filter(lambda x: exists(join(self.path.abspath(), x)), pkgsDirs))
        
        # add targets
        targets = self.targets.split(',')
        targets.extend(pkgsTargets)
        targets = self.removeDuplicates(targets)
        self.targets = ','.join(targets)
        
        # deliver certain things in main directory regarless
        if env['DELIVER_SOURCE'] is True: 
            for x in pkgsIncludes :
                if os.path.isdir(join(self.path.abspath(), x)) :
                    self.copyTree(join(self.path.abspath(), x), join(env['PREFIX'], 'source', x), pkgsExcludes, env['PREFIX'])
                else :
                    self.install_files(join(env['PREFIX'], 'source', os.path.split(x)[0]), x)

    def install_tgt(tsk, **modArgs):
        # The main purpose this serves is to recursively copy all the wscript's
        # involved when we have a wscript whose sole job is to install files
        modArgs = dict((k.lower(), v) for k, v in modArgs.iteritems())
        if 'env' in modArgs:
            env = modArgs['env']
        else:
            variant = modArgs.get('variant', tsk.env['VARIANT'] or 'default')
            env = tsk.all_envs[variant]

        features = 'install_tgt'
        if env['install_source']:
            targetsToAdd = modArgs.get('targets_to_add', [])
            targetsToAdd = targetsToAdd + getWscriptTargets(tsk, env, tsk.path)
            modArgs['targets_to_add'] = targetsToAdd
            features += ' add_targets'
        tsk(features = features, **modArgs)

    def module(self, **modArgs):
        """
        Builds a module, along with optional tests.
        It makes assumptions, but most can be overridden by passing in args.
        """
        bld = self
        if 'env' in modArgs:
            env = modArgs['env']
        else:
            variant = modArgs.get('variant', bld.env['VARIANT'] or 'default')
            env = bld.all_envs[variant]
    
        modArgs = dict((k.lower(), v) for k, v in modArgs.iteritems())
        
        for func in self.module_hooks:
            func(modArgs, env)

        lang = modArgs.get('lang', 'c++')
        libExeType = {'c++':'cxx', 'c':'c'}.get(lang, 'cxx')
        sourceExt = {'c++':'.cpp', 'c':'.c'}.get(lang, 'cxx')
        if modArgs.get('nosuffix', False) :
            libName = modArgs['name']
        else :
            libName = '%s-%s' % (modArgs['name'], lang)
        path = modArgs.get('path',
                           'dir' in modArgs and bld.path.find_dir(modArgs['dir']) or bld.path)

        module_deps = map(lambda x: '%s-%s' % (x, lang), listify(modArgs.get('module_deps', '')))
        defines = self.__getDefines(env) + listify(modArgs.get('defines', ''))
        uselib_local = module_deps + listify(modArgs.get('uselib_local', '')) + listify(modArgs.get('use',''))
        uselib = listify(modArgs.get('uselib', '')) + ['CSTD', 'CRUN']
        targets_to_add = listify(modArgs.get('targets_to_add', ''))
        includes = listify(modArgs.get('includes', 'include'))
        exportIncludes = listify(modArgs.get('export_includes', 'include'))
        libVersion = modArgs.get('version', None)
        installPath = modArgs.get('install_path', None)

        # This specifies that we need to check if it is a USELIB or USELIB_LOCAL
        # If MAKE_%% is defined, then it is local; otherwise, it's a uselib
        # If we're doing a source installation and we built it locally, the
        # source target already got added on as a dependency.  If we didn't
        # build it locally, we need to add the source target on here since
        # in that case this module doesn't depend on a task associated with
        # the external library.
        uselibCheck = modArgs.get('uselib_check', None)
        if uselibCheck:
            for currentLib in listify(uselibCheck):
                if ('MAKE_%s' % currentLib) in env:
                    uselib_local += [currentLib]
                else:
                    uselib += [currentLib]
                    if env['install_source']:
                        sourceTarget = '%s_SOURCE_INSTALL' % currentLib
                        targets_to_add += [sourceTarget]
        
        # this specifies that we need to check if it is a USELIB or USELIB_LOCAL
        # if MAKE_%% is defined, then it is local; otherwise, it's a uselib
        uselibCheck = modArgs.pop('uselib_check', None)
        if uselibCheck:
            if ('MAKE_%s' % uselibCheck) in env:
                uselib_local.append(uselibCheck)
            else:
                uselib.append(uselibCheck)

        if libVersion is not None and sys.platform != 'win32':
            targetName = '%s.%s' % (libName, self.safeVersion(libVersion))
        else:
            targetName = libName
        
        allSourceExt = listify(modArgs.get('source_ext', '')) + [sourceExt]
        sourcedirs = listify(modArgs.get('source_dir', modArgs.get('sourcedir', 'source')))
        glob_patterns = []
        for dir in sourcedirs:
            for ext in allSourceExt:
                glob_patterns.append(join(dir, '*%s' % ext))
        
        #build the lib
        lib = bld(features='%s %s%s add_targets includes'% (libExeType, libExeType, env['LIB_TYPE'] or 'stlib'), includes=includes,
                target=targetName, name=libName, export_includes=exportIncludes,
                use=uselib_local, uselib=uselib, env=env.derive(),
                defines=defines, path=path,
                source=path.ant_glob(glob_patterns), targets_to_add=targets_to_add)
        lib.source = filter(partial(lambda x, t: basename(str(t)) not in x, modArgs.get('source_filter', '').split()), lib.source)
        
        if env['install_libs']:
            lib.install_path = installPath or '${PREFIX}/lib'
        
        if not lib.source:
            lib.features = 'add_targets includes'
        
        pattern = env['%s%s_PATTERN' % (libExeType, env['LIB_TYPE'] or 'stlib')]
        if libVersion is not None and sys.platform != 'win32' and Options.options.symlinks and env['install_libs'] and lib.source:
            symlinkLoc = '%s/%s' % (lib.install_path, pattern % libName)
            lib.targets_to_add.append(bld(features='symlink_as_tgt', dest=symlinkLoc, src=pattern % lib.target, name='%s-symlink' % libName))
        
        if env['install_headers']:
            incNode = path.make_node('include')
            relpath = incNode.path_from(path)
            lib.targets_to_add.append(bld(features='install_tgt', pattern='**/*',
                    dir=incNode, install_path='${PREFIX}/%s' % relpath))

        addSourceTargets(bld, env, path, lib)

        testNode = path.make_node('tests')
        if os.path.exists(testNode.abspath()) and not Options.options.libs_only:
            test_deps = listify(modArgs.get('test_deps', modArgs.get('module_deps', '')))
            
            test_deps.append(modArgs['name'])
                
            test_deps = map(lambda x: '%s-%s' % (x, lang), test_deps + listify(modArgs.get('test_uselib_local', '')) + listify(modArgs.get('test_use','')))
            
            for test in testNode.ant_glob('*%s' % sourceExt):
                if str(test) not in listify(modArgs.get('test_filter', '')):
                    testName = splitext(str(test))[0]
                    self.program(env=env.derive(), name=testName, target=testName, source=str(test),
                                 use=test_deps,
                                 uselib=modArgs.get('test_uselib', uselib),
                                 lang=lang, path=testNode, includes=includes, defines=defines,
                                 install_path='${PREFIX}/tests/%s' % modArgs['name'])

        testNode = path.make_node('unittests')
        if os.path.exists(testNode.abspath()) and not Options.options.libs_only:
            test_deps = listify(modArgs.get('unittest_deps', modArgs.get('module_deps', '')))
            test_uselib = listify(modArgs.get('unittest_uselib', uselib))
            
            test_deps.append(modArgs['name'])
            
            if 'INCLUDES_UNITTEST' in env:
                includes.append(env['INCLUDES_UNITTEST'][0])

                test_deps = map(lambda x: '%s-%s' % (x, lang), test_deps + listify(modArgs.get('test_uselib_local', '')) + listify(modArgs.get('test_use','')))
            
                sourceExt = {'c++':'.cpp', 'c':'.c'}.get(lang, 'cxx')
                tests = []
                for test in testNode.ant_glob('*%s' % sourceExt):
                    if str(test) not in listify(modArgs.get('unittest_filter', '')):
                        testName = splitext(str(test))[0]
                        exe = self(features='%s %sprogram' % (libExeType, libExeType), 
                                     env=env.derive(), name=testName, target=testName, source=str(test), use=test_deps,
                                     uselib = modArgs.get('unittest_uselib', modArgs.get('uselib', '')),
                                     lang=lang, path=testNode, defines=defines,
                                     includes=includes,
                                     install_path='${PREFIX}/unittests/%s' % modArgs['name'])
                        if Options.options.unittests or Options.options.all_tests:
                            exe.features += ' test'

                        tests.append(testName)
                
                # add a post-build hook to run the unit tests
                # I use partial so I can pass arguments to a post build hook
                #if Options.options.unittests:
                #    bld.add_post_fun(partial(CPPBuildContext.runUnitTests,
                #                             tests=tests,
                #                             path=self.getBuildDir(testNode)))

        confDir = path.make_node('conf')
        if exists(confDir.abspath()):
            lib.targets_to_add.append(
                    bld(features='install_tgt', dir=confDir, pattern='**',
                        install_path='${PREFIX}/share/%s/conf' % modArgs['name'],
                        copy_to_source_dir=True))

        return env
    
    
    def plugin(self, **modArgs):
        """
        Builds a plugin (.so) and sets the install path based on the type of
        plugin (via the plugin kwarg).
        """
        bld = self
        if 'env' in modArgs:
            env = modArgs['env'].derive()
        else:
            variant = modArgs.get('variant', bld.env['VARIANT'] or 'default')
            env = bld.all_envs[variant].derive()
        
        modArgs = dict((k.lower(), v) for k, v in modArgs.iteritems())
        lang = modArgs.get('lang', 'c++')
        libExeType = {'c++':'cxx', 'c':'c'}.get(lang, 'cxx')
        libName = modArgs.get('libname', '%s-%s' % (modArgs['name'], lang))
        plugin = modArgs.get('plugin', '')
        path = modArgs.get('path',
                           'dir' in modArgs and bld.path.find_dir(modArgs['dir']) or bld.path)

        module_deps = map(lambda x: '%s-%s' % (x, lang), listify(modArgs.get('module_deps', '')))
        defines = self.__getDefines(env) + listify(modArgs.get('defines', '')) + ['PLUGIN_MODULE_EXPORTS']
        uselib_local = module_deps + listify(modArgs.get('uselib_local', '')) + listify(modArgs.get('use',''))
        uselib = listify(modArgs.get('uselib', '')) + ['CSTD', 'CRUN']
        targets_to_add = listify(modArgs.get('targets_to_add', ''))
        includes = listify(modArgs.get('includes', 'include'))
        exportIncludes = listify(modArgs.get('export_includes', 'include'))
        source = listify(modArgs.get('source', '')) or None
        removePluginPrefix = modArgs.get('removepluginprefix', False)

        # This is so that on Unix we name the plugins without the 'lib' prefix
        if removePluginPrefix:
            if env['cshlib_PATTERN'].startswith('lib'):
                env['cshlib_PATTERN'] = env['cshlib_PATTERN'][3:]
            if env['cxxshlib_PATTERN'].startswith('lib'):
                env['cxxshlib_PATTERN'] = env['cxxshlib_PATTERN'][3:]
        
        lib = bld(features='%s %sshlib add_targets no_implib' % (libExeType, libExeType),
                target=libName, name=libName, source=source,
                includes=includes, export_includes=exportIncludes,
                use=uselib_local, uselib=uselib, env=env.derive(),
                defines=defines, path=path, targets_to_add=targets_to_add,
                install_path='${PREFIX}/share/%s/plugins' % plugin)

        sourceExt = {'c++':'.cpp', 'c':'.c'}.get(lang, 'cxx')
        allSourceExt = listify(modArgs.get('source_ext', '')) + [sourceExt]
        sourcedirs = listify(modArgs.get('source_dir', modArgs.get('sourcedir', 'source')))
        glob_patterns = []
        for dir in sourcedirs:
            for ext in allSourceExt:
                glob_patterns.append(join(dir, '*%s' % ext))

        if not source:
            lib.source = path.ant_glob(glob_patterns)
            lib.source = filter(partial(lambda x, t: basename(str(t)) not in x, modArgs.get('source_filter', '').split()), lib.source)
        if env['install_headers']:
            incNode = path.make_node('include')
            relpath = incNode.path_from(path)
            lib.targets_to_add.append(bld(features='install_tgt', pattern='**/*',
                    dir=incNode, install_path='${PREFIX}/%s' % relpath))

        addSourceTargets(self, env, path, lib)
        
        confDir = path.make_node('conf')
        if exists(confDir.abspath()):
            lib.targets_to_add.append(
                    bld(features='install_tgt', dir=confDir, pattern='**',
                        install_path='${PREFIX}/share/%s/conf' % plugin,
                        copy_to_source_dir=True))

        pluginsTarget = '%s-plugins' % plugin
        try:
            bld.get_tgen_by_name(pluginsTarget).targets_to_add.append(libName)
        except:
            bld(target=pluginsTarget,
                features='add_targets', targets_to_add=[libName])

    def program_helper(self, **modArgs):
        """
        Builds a program (exe)
        """
        bld = self
        if 'env' in modArgs:
            env = modArgs['env']
        else:
            variant = modArgs.get('variant', bld.env['VARIANT'] or 'default')
            env = bld.all_envs[variant]
        
        modArgs = dict((k.lower(), v) for k, v in modArgs.iteritems())
        lang = modArgs.get('lang', 'c++')
        libExeType = {'c++':'cxx', 'c':'c'}.get(lang, 'cxx')
        progName = modArgs['name']
        path = modArgs.get('path',
                           'dir' in modArgs and bld.path.find_dir(modArgs['dir']) or bld.path)

        module_deps = map(lambda x: '%s-%s' % (x, lang), listify(modArgs.get('module_deps', '')))
        defines = self.__getDefines(env) + listify(modArgs.get('defines', ''))
        uselib_local = module_deps + listify(modArgs.get('uselib_local', '')) + listify(modArgs.get('use',''))
        uselib = listify(modArgs.get('uselib', '')) + ['CSTD', 'CRUN']
        targets_to_add = listify(modArgs.get('targets_to_add', ''))
        includes = listify(modArgs.get('includes', 'include'))
        source = listify(modArgs.get('source', '')) or None
        install_path = modArgs.get('install_path', '${PREFIX}/bin')
        
        if not source:
            source = bld.path.make_node(modArgs.get('source_dir', modArgs.get('sourcedir', 'source'))).ant_glob('*.c*', excl=modArgs.get('source_filter', ''))
        
        exe = bld.program(features = 'add_targets',
                               source=source, name=progName,
                               includes=includes, defines=defines,
                               use=uselib_local, uselib=uselib,
                               env=env.derive(), target=progName, path=path,
                               install_path=install_path,
                               targets_to_add=targets_to_add)

        addSourceTargets(bld, env, path, exe)

        return exe

    
    def getBuildDir(self, path=None):
        """
        Returns the build dir, relative to where you currently are (bld.path)
        """
        if path is None:
            path = self.path
        return path.find_or_declare('.').abspath()

    def mexify(self, **modArgs):
        """
        Utility for compiling a mex file (with mexFunction) to a mex shared lib
        """
        bld = self
        if 'env' in modArgs:
            env = modArgs['env']
        else:
            variant = modArgs.get('variant', bld.env['VARIANT'] or 'default')
            env = bld.all_envs[variant]
        
        if self.is_defined('HAVE_MEX_H'):
        
            modArgs = dict((k.lower(), v) for k, v in modArgs.iteritems())
            lang = modArgs.get('lang', 'c++')
            libExeType = {'c++':'cxx', 'c':'c'}.get(lang, 'cxx')
            path = modArgs.get('path',
                               'dir' in modArgs and bld.path.find_dir(modArgs['dir']) or bld.path)
                               
            #override the shlib pattern
            env = env.derive()
            shlib_pattern = '%sshlib_PATTERN' % libExeType
            if env[shlib_pattern].startswith('lib'):
                env[shlib_pattern] = env[shlib_pattern][3:]
            env[shlib_pattern] = splitext(env[shlib_pattern])[0] + env['MEX_EXT']

            module_deps = map(lambda x: '%s-%s' % (x, lang), listify(modArgs.get('module_deps', '')))
            defines = self.__getDefines(env) + listify(modArgs.get('defines', ''))
            uselib_local = module_deps + listify(modArgs.get('uselib_local', '')) + listify(modArgs.get('use',''))
            uselib = listify(modArgs.get('uselib', '')) + ['CSTD', 'CRUN', 'MEX']
            includes = listify(modArgs.get('includes', 'include'))
            installPath = modArgs.get('install_path', None)
            source = modArgs.get('source', None)
            name = modArgs.get('name', None)
            targetName = modArgs.get('target', None)
            
            if source:
                name = splitext(split(source)[1])[0]
            
            mex = bld(features='%s %sshlib'%(libExeType, libExeType), target=targetName or name,
                                   name=name, use=uselib_local,
                                   uselib=uselib, env=env.derive(), defines=defines,
                                   path=path, source=source, includes=includes,
                                   install_path=installPath or '${PREFIX}/mex')
            if not source:
                mex.source = path.ant_glob(modArgs.get('source_dir', modArgs.get('sourcedir', 'source')) + '/*')
                mex.source = filter(partial(lambda x, t: basename(str(t)) not in x, modArgs.get('source_filter', '').split()), lib.source)            
            pattern = env['%s_PATTERN' % (env['LIB_TYPE'] or 'staticlib')]
    


class GlobDirectoryWalker:
    """ recursively walk a directory, matching filenames """
    def __init__(self, directory, patterns=["*"]):
        self.stack = [directory]
        self.patterns = patterns
        self.files = []
        self.index = 0
        
    def __iter__(self):
        return self.next()
    
    def next(self):
        while True:
            try:
                file = self.files[self.index]
                self.index = self.index + 1
            except IndexError:
                # pop next directory from stack
                if len(self.stack) == 0:
                    raise StopIteration
                self.directory = self.stack.pop()
                if isdir(self.directory):
                    self.files = os.listdir(self.directory)
                else:
                    self.files, self.directory = [self.directory], ''
                self.index = 0
            else:
                # got a filename
                fullname = join(self.directory, file)
                if isdir(fullname):# and not os.path.islink(fullname):
                    self.stack.append(fullname)
                for p in self.patterns:
                    if fnmatch.fnmatch(file, p):
                        yield fullname

def recursiveGlob(directory, patterns=["*"]):
    return GlobDirectoryWalker(directory, patterns)


def getPlatform(pwd=None, default=None):
    """ returns the platform name """
    platform = default or sys.platform
    
    if platform != 'win32':
        if not pwd:
            pwd = os.getcwd()
            
        locs = recursiveGlob(pwd, patterns=['config.guess'])
        for loc in locs:
            if not exists(loc): continue
            try:
                out = os.popen('chmod +x %s' % loc)
                out.close()
            except:{}
            try:
                out = os.popen(loc, 'r')
                platform = out.readline()
                platform = platform.strip('\n')
                out.close()
            except:{}
            else:
                break
    return platform



import zipfile
def unzipper(inFile, outDir):
    if not outDir.endswith(':') and not exists(outDir):
        os.mkdir(outDir)
    
    zf = zipfile.ZipFile(inFile)
    
    dirs = filter(lambda x: x.endswith('/'), zf.namelist())
    dirs.sort()
    
    for d in filter(lambda x: not exists(x),
                    map(lambda x: join(outDir, x), dirs)):
        os.mkdir(d)

    for i, name in enumerate(filter(lambda x: not x.endswith('/'), zf.namelist())):
        outFile = open(join(outDir, name), 'wb')
        outFile.write(zf.read(name))
        outFile.flush()
        outFile.close()
        
def options(opt):
    opt.load('compiler_cc')
    opt.load('compiler_cxx')
    opt.load('waf_unit_test')

    if sys.version_info >= (2,5,0):
      opt.load('msvs')
    
    if Options.platform == 'win32':
        opt.load('msvc')
        opt.add_option('--with-crt', action='store', choices=['MD', 'MT'],
                       dest='crt', default='MD', help='Specify Windows CRT library - MT or MD (default)')
    
    opt.add_option('--packages', action='store', dest='packages',
                   help='Target packages to build (common-separated list)')
    opt.add_option('--dist-source', action='store_true', dest='dist_source', default=False,
                   help='Distribute source into the installation area (for delivering source)')
    opt.add_option('--disable-warnings', action='store_false', dest='warnings',
                   default=True, help='Disable warnings')
    opt.add_option('--warnings-as-errors', action='store_true', dest='warningsAsErrors',
                   default=False, help='Treat compiler warnings as errors')
    opt.add_option('--enable-debugging', action='store_true', dest='debugging',
                   help='Enable debugging')
    #TODO - get rid of enable64 - it's useless now
    opt.add_option('--enable-64bit', action='store_true', dest='enable64',
                   help='Enable 64bit builds')
    opt.add_option('--enable-32bit', action='store_true', dest='enable32',
                   help='Enable 32bit builds')
    opt.add_option('--with-cflags', action='store', nargs=1, dest='cflags',
                   help='Set non-standard CFLAGS', metavar='FLAGS')
    opt.add_option('--with-cxxflags', action='store', nargs=1, dest='cxxflags',
                   help='Set non-standard CXXFLAGS (C++)', metavar='FLAGS')
    opt.add_option('--with-linkflags', action='store', nargs=1, dest='linkflags',
                   help='Set non-standard LINKFLAGS (C/C++)', metavar='FLAGS')
    opt.add_option('--with-defs', action='store', nargs=1, dest='_defs',
                   help='Use DEFS as macro definitions', metavar='DEFS')
    opt.add_option('--with-optz', action='store',
                   choices=['med', 'fast', 'fastest'],
                   default='fastest', metavar='OPTZ',
                   help='Specify the optimization level for optimized/release builds')
    opt.add_option('--libs-only', action='store_true', dest='libs_only',
                   help='Only build the libs (skip building the tests, etc.)')
    opt.add_option('--shared', action='store_true', dest='shared_libs',
                   help='Build all libs as shared libs')
    opt.add_option('--disable-symlinks', action='store_false', dest='symlinks',
                   default=True, help='Disable creating symlinks for libs')
    opt.add_option('--unittests', action='store_true', dest='unittests',
                   help='Build-time option to run unit tests after the build has completed')
    opt.add_option('--no-headers', action='store_false', dest='install_headers',
                    default=True, help='Don\'t install module headers')
    opt.add_option('--no-libs', action='store_false', dest='install_libs',
                    default=True, help='Don\'t install module libraries')
    opt.add_option('--install-source', action='store_true', dest='install_source', default=False,
                   help='Distribute source into the installation area (for delivering source)')
    

types_str = '''
#include <stdio.h>
int isBigEndian()
{
    long one = 1;
    return !(*((char *)(&one)));
}
int main()
{
    if (isBigEndian()) printf("bigendian=True\\n");
    else printf("bigendian=False\\n");
    printf("sizeof_int=%d\\n", sizeof(int));
    printf("sizeof_short=%d\\n", sizeof(short));
    printf("sizeof_long=%d\\n", sizeof(long));
    printf("sizeof_long_long=%d\\n", sizeof(long long));
    printf("sizeof_float=%d\\n", sizeof(float));
    printf("sizeof_double=%d\\n", sizeof(double));
    return 0;
}
'''

def configure(self):
    
    if self.env['DETECTED_BUILD_PY']:
        return
    
    sys_platform = getPlatform(default=Options.platform)
    appleRegex = r'i.86-apple-.*'
    linuxRegex = r'.*-.*-linux-.*|i686-pc-.*|linux'
    solarisRegex = r'sparc-sun.*|i.86-pc-solaris.*|sunos'
    winRegex = r'win32'
    
    # build packages is a map of maps
    self.env['BUILD_PACKAGES'] = {}

    # store in the environment whether the user wants to
    # deliver source into the installation area --
    # this can also be a build time argument if placed in
    # the top level wscript
    self.env['DELIVER_SOURCE'] = Options.options.dist_source
    
    self.msg('Platform', sys_platform, color='GREEN')
    
    # Dirty fix to get around libpath problems..
    if re.match(winRegex, sys_platform):
        real_cmd_and_log = self.cmd_and_log
        def wrap_cmd_and_log(*k, **kw):
            sout = real_cmd_and_log(*k, **kw)
            if sout:
                lines=sout.splitlines()
                if not lines[0]:lines=lines[1:]
                for line in lines[1:]:
                    if line.startswith('LIB='):
                        for i in line[4:].split(';'):
                            if i:
                                if not os.path.exists(i):
                                    self.fatal('libpath does not exist')
            return sout
        self.cmd_and_log = wrap_cmd_and_log
        
        # If we're in the Windows SDK or VS command prompt, having these set can mess things up.
        env_lib = self.environ.get('LIB', None)
        if 'LIB' in self.environ: del self.environ['LIB']
        env_cl = os.environ.get('CL', None)
        if 'CL' in os.environ: del os.environ['CL']
    
        if Options.options.enable64 or ('64' in platform.machine() and not Options.options.enable32):
            self.env['MSVC_TARGETS'] = ['x64']
            
            # Look for 32-bit msvc if we don't find 64-bit.
            if not Options.options.enable64:
                self.options.check_c_compiler = self.options.check_cxx_compiler = 'msvc'
                try:
                    self.load('compiler_c')
                except self.errors.ConfigurationError:
                    self.env['MSVC_TARGETS'] = None
                    self.tool_cache.remove(('msvc',id(self.env),None))
                    self.tool_cache.remove(('compiler_c',id(self.env),None))
                    self.msg('Checking for \'msvc\'', 'Warning: cound not find x64 msvc, looking for others', color='RED')
        else:
            self.env['MSVC_TARGETS'] = ['x86']

    self.load('compiler_c')
    self.load('compiler_cxx')
    self.load('waf_unit_test')
    
    # Reset cmd_and_log
    if re.match(winRegex, sys_platform):
        self.cmd_and_log = real_cmd_and_log
        if env_lib is not None: self.environ['LIB'] = env_lib
        if env_cl is not None: os.environ['CL'] = env_cl
    
    cxxCompiler = self.env["COMPILER_CXX"]
    ccCompiler = self.env["COMPILER_CC"]
    
    if ccCompiler == 'msvc':
        cxxCompiler = ccCompiler
        
    if not cxxCompiler or not ccCompiler:
        self.fatal('Unable to find C/C++ compiler')
    
    #Look for a ton of headers
    self.check_cc(header_name="inttypes.h", mandatory=False)
    self.check_cc(header_name="unistd.h", mandatory=False)
    self.check_cc(header_name="getopt.h", mandatory=False)
    self.check_cc(header_name="malloc.h", mandatory=False)
    self.check_cc(header_name="sys/time.h", mandatory=False)
    self.check_cc(header_name="dlfcn.h", mandatory=False)
    self.check_cc(header_name="fcntl.h", mandatory=False)
    self.check_cc(header_name="check.h", mandatory=False)
    self.check_cc(header_name="memory.h", mandatory=False)
    self.check_cc(header_name="string.h", mandatory=False)
    self.check_cc(header_name="strings.h", mandatory=False)
    self.check_cc(header_name="stdbool.h", mandatory=False)
    self.check_cc(header_name="stdlib.h", mandatory=False)
    self.check_cc(header_name="stddef.h", mandatory=False)
    self.check_cc(function_name='localtime_r', header_name="time.h", mandatory=False)
    self.check_cc(function_name='gmtime_r', header_name="time.h", mandatory=False)
    self.check_cc(function_name='mmap', header_name="sys/mman.h", mandatory=False)
    self.check_cc(function_name='memmove', header_name="string.h", mandatory=False)
    self.check_cc(function_name='strerror', header_name="string.h", mandatory=False)
    self.check_cc(function_name='bcopy', header_name="strings.h", mandatory=False)
    self.check_cc(type_name='size_t', header_name='stddef.h', mandatory=False)
    self.check_cc(fragment='int main(){const int i = 0; return 0;}',
                  define_name='HAVE_CONST', msg='Checking for const keyword', mandatory=False)
    self.check_cc(fragment='int main(){unsigned short; return 0;}',
                  define_name='HAVE_UNSIGNED_SHORT', msg='Checking for unsigned short', mandatory=False)
    self.check_cc(fragment='int main(){unsigned char i; return 0;}',
                  define_name='HAVE_UNSIGNED_CHAR', msg='Checking for unsigned char', mandatory=False)
    self.check_cc(lib="m", mandatory=False, uselib_store='MATH')
    self.check_cc(lib="rt", mandatory=False, uselib_store='RT')
    self.check_cc(lib="sqrt", mandatory=False, uselib_store='SQRT')
    self.check_cc(function_name='erf', header_name="math.h", use = "MATH", mandatory=False)
    self.check_cc(function_name='erff', header_name="math.h", use = "MATH", mandatory=False)
    
    self.check_cc(function_name='gettimeofday', header_name='sys/time.h', mandatory=False)
    if self.check_cc(lib='rt', function_name='clock_gettime', header_name='time.h', mandatory=False):
        self.env.DEFINES.append('USE_CLOCK_GETTIME')
    self.check_cc(function_name='BSDgettimeofday', header_name='sys/time.h', mandatory=False)
    self.check_cc(function_name='gethrtime', header_name='sys/time.h', mandatory=False)
    self.check_cc(function_name='getpagesize', header_name='unistd.h', mandatory=False)
    self.check_cc(function_name='getopt', header_name='unistd.h', mandatory=False)
    self.check_cc(function_name='getopt_long', header_name='getopt.h', mandatory=False)
    
    self.check_cc(fragment='#include <math.h>\nint main(){if (!isnan(3.14159)) isnan(2.7183);}',
                  define_name='HAVE_ISNAN', msg='Checking for function isnan',
                  errmsg='not found', mandatory=False)
    
    # Check for hrtime_t data type; some systems (AIX) seem to have
    # a function called gethrtime but no hrtime_t!
    frag = '''
    #ifdef HAVE_SYS_TIME_H
    #include <sys/time.h>
    int main(){hrtime_t foobar;}
    #endif
    '''
    self.check_cc(fragment=frag, define_name='HAVE_HRTIME_T',
                  msg='Checking for type hrtime_t', errmsg='not found', mandatory=False)
    
    
    #find out the size of some types, etc.
    output = self.check(fragment=types_str, execute=1, msg='Checking system type sizes', define_ret=True)
    t = Utils.str_to_dict(output or '')
    for k, v in t.iteritems():
        try:
            v = int(v)
        except:
            v = v.strip()
            if v == 'True':
                v = True
            elif v == 'False':
                v = False
        #v = eval(v)
        self.msg(k.replace('_', ' '), str(v))
        self.define(k.upper(), v)
    
    env = self.env
    env['PLATFORM'] = sys_platform
    
    env['LIB_TYPE'] = Options.options.shared_libs and 'shlib' or 'stlib'
    
    env['install_headers'] = Options.options.install_headers
    env['install_libs'] = Options.options.install_libs
    env['install_source'] = Options.options.install_source

    if Options.options.cxxflags:
        env.append_unique('CXXFLAGS', Options.options.cxxflags.split())
    if Options.options.cflags:
        env.append_unique('CFLAGS', Options.options.cflags.split())
    if Options.options.linkflags:
        env.append_unique('LINKFLAGS', Options.options.linkflags.split())
    if Options.options._defs:
        env.append_unique('DEFINES', Options.options._defs.split(','))
    
    config = {'cxx':{}, 'cc':{}}

    #apple
    if re.match(appleRegex, sys_platform):
        env.append_value('LIB_DL', 'dl')
        env.append_value('LIB_NSL', 'nsl')
        env.append_value('LIB_THREAD', 'pthread')
        self.check_cc(lib='pthread', mandatory=True)

        config['cxx']['debug']          = '-g'
        config['cxx']['warn']           = '-Wall'
        config['cxx']['verbose']        = '-v'
        config['cxx']['64']             = '-m64'
        config['cxx']['32']             = '-m32'
        config['cxx']['optz_med']       = '-O1'
        config['cxx']['optz_fast']      = '-O2'
        config['cxx']['optz_fastest']   = '-O3'

        #env.append_value('LINKFLAGS', '-fPIC -dynamiclib'.split())
        env.append_value('LINKFLAGS', '-fPIC'.split())
        env.append_value('CXXFLAGS', '-fPIC')
        env.append_value('CXXFLAGS_THREAD', '-D_REENTRANT')

        config['cc']['debug']          = config['cxx']['debug']
        config['cc']['warn']           = config['cxx']['warn']
        config['cc']['verbose']        = config['cxx']['verbose']
        config['cc']['64']             = config['cxx']['64']
        config['cc']['optz_med']       = config['cxx']['optz_med']
        config['cc']['optz_fast']      = config['cxx']['optz_fast']
        config['cc']['optz_fastest']   = config['cxx']['optz_fastest']

        env.append_value('DEFINES', '_FILE_OFFSET_BITS=64 _LARGEFILE_SOURCE __POSIX'.split())
        env.append_value('CFLAGS', '-fPIC -dynamiclib'.split())
        env.append_value('CFLAGS_THREAD', '-D_REENTRANT')

    #linux
    elif re.match(linuxRegex, sys_platform):
        env.append_value('LIB_DL', 'dl')
        env.append_value('LIB_NSL', 'nsl')
        env.append_value('LIB_THREAD', 'pthread')
        env.append_value('LIB_MATH', 'm')

        self.check_cc(lib='pthread', mandatory=True)

        warningFlags = '-Wall'
        if Options.options.warningsAsErrors:
            warningFlags += ' -Wfatal-errors'

        if cxxCompiler == 'g++':
            config['cxx']['debug']          = '-g'
            config['cxx']['warn']           = warningFlags.split()
            config['cxx']['verbose']        = '-v'
            config['cxx']['64']             = '-m64'
            config['cxx']['32']             = '-m32'
            config['cxx']['linkflags_64']   = '-m64'
            config['cxx']['linkflags_32']   = '-m32'
            config['cxx']['optz_med']       = '-O1'
            config['cxx']['optz_fast']      = '-O2'
            config['cxx']['optz_fastest']   = '-O3'
            
            env.append_value('DEFINES', '_FILE_OFFSET_BITS=64 _LARGEFILE_SOURCE __POSIX'.split())
            env.append_value('LINKFLAGS', '-Wl,-E -fPIC'.split())
            env.append_value('CXXFLAGS', '-fPIC')
            
            #for some reason using CXXDEFINES_THREAD won't work w/uselib... so using FLAGS instead
            env.append_value('CXXFLAGS_THREAD', '-D_REENTRANT')
        
        if ccCompiler == 'gcc':
            config['cc']['debug']          = '-g'
            config['cc']['warn']           = warningFlags.split()
            config['cc']['verbose']        = '-v'
            config['cc']['64']             = '-m64'
            config['cc']['32']             = '-m32'
            config['cc']['linkflags_64']   = '-m64'
            config['cc']['linkflags_32']   = '-m32'
            config['cc']['optz_med']       = '-O1'
            config['cc']['optz_fast']      = '-O2'
            config['cc']['optz_fastest']   = '-O3'
            
            #env.append_value('DEFINES', '_FILE_OFFSET_BITS=64 _LARGEFILE_SOURCE __POSIX'.split())
            env.append_value('CFLAGS', '-fPIC'.split())
            
            #for some reason using CXXDEFINES_THREAD won't work w/uselib... so using FLAGS instead
            env.append_value('CFLAGS_THREAD', '-D_REENTRANT')
    
    #Solaris
    elif re.match(solarisRegex, sys_platform):
        env.append_value('LIB_DL', 'dl')
        env.append_value('LIB_NSL', 'nsl')
        env.append_value('LIB_SOCKET', 'socket')
        env.append_value('LIB_THREAD', 'thread')
        env.append_value('LIB_MATH', 'm')
        env.append_value('LIB_CRUN', 'Crun')
        env.append_value('LIB_CSTD', 'Cstd')
        self.check_cc(lib='thread', mandatory=True)
        self.check_cc(header_name="atomic.h")
        
        warningFlags = ''
        if Options.options.warningsAsErrors:
            warningFlags = '-errwarn=%all'

        if cxxCompiler == 'sunc++':
            (bitFlag32, bitFlag64) = getSolarisFlags(env['CXX'][0])
            config['cxx']['debug']          = '-g'
            config['cxx']['warn']           = warningFlags.split()
            config['cxx']['nowarn']         = '-erroff=%all'
            config['cxx']['verbose']        = '-v'
            config['cxx']['64']             = bitFlag64
            config['cxx']['32']             = bitFlag32
            config['cxx']['linkflags_32']   = bitFlag32
            config['cxx']['linkflags_64']   = bitFlag64
            config['cxx']['optz_med']       = '-xO3'
            config['cxx']['optz_fast']      = '-xO4'
            config['cxx']['optz_fastest']   = '-xO5'
            env['CXXFLAGS_cxxshlib']        = ['-KPIC', '-DPIC']

            env.append_value('DEFINES', '_FILE_OFFSET_BITS=64 _LARGEFILE_SOURCE'.split())
            env.append_value('CXXFLAGS', '-KPIC -instances=global'.split())
            env.append_value('CXXFLAGS_THREAD', '-mt')
            
        if ccCompiler == 'suncc':
            (bitFlag32, bitFlag64) = getSolarisFlags(env['CC'][0])
            config['cc']['debug']          = '-g'
            config['cc']['warn']           = warningFlags.split()
            config['cc']['nowarn']         = '-erroff=%all'
            config['cc']['verbose']        = '-v'
            config['cc']['64']             = bitFlag64
            config['cc']['linkflags_64']   = bitFlag64
            config['cc']['linkflags_32']   = bitFlag32
            config['cc']['32']             = bitFlag32
            config['cc']['optz_med']       = '-xO3'
            config['cc']['optz_fast']      = '-xO4'
            config['cc']['optz_fastest']   = '-xO5'
            env['CFLAGS_cshlib']           = ['-KPIC', '-DPIC']

            #env.append_value('DEFINES', '_FILE_OFFSET_BITS=64 _LARGEFILE_SOURCE'.split())
            env.append_value('CFLAGS', '-KPIC'.split())
            env.append_value('CFLAGS_THREAD', '-mt')

    elif re.match(winRegex, sys_platform):
#        if Options.options.enable64:
#            platform = 'win'

        env.append_value('LIB_RPC', 'rpcrt4')
        env.append_value('LIB_SOCKET', 'Ws2_32')
        
        winRegex
        crtFlag = '/%s' % Options.options.crt
        crtDebug = '%sd' % crtFlag

        # Sets the size of the stack (in bytes)
        stackFlag = '/STACK:80000000'

        # Skipping warning 4290 about how VS doesn't implement exception
        # specifications properly.  For warnings, use /W4 because /Wall
        # gives us tons of warnings in the VS headers themselves
        warningFlags = '/W4 /wd4290'
        if Options.options.warningsAsErrors:
            warningFlags += ' /WX'

        vars = {}
        vars['debug']          = ['/Zi', crtDebug]
        vars['warn']           = warningFlags.split()
        vars['nowarn']         = '/w'
        vars['verbose']        = ''
        vars['optz_med']       = ['-O2', crtFlag]
        vars['optz_fast']      = ['-O2', crtFlag]
        vars['optz_fastest']   = ['-Ox', crtFlag]
        # The MACHINE flag is is probably not actually necessary
        # The linker should be able to infer it from the object files
        # But doing this just to make sure we're really building 32/64 bit
        # applications
        vars['linkflags_32'] = [stackFlag, '/MACHINE:X86']
        vars['linkflags_64'] = [stackFlag, '/MACHINE:X64']

        if Options.options.debugging:
            # In order to generate a .pdb file, we need both the /Zi 
            # compilation flag and the /DEBUG linker flag
            vars['linkflags_32'].append('/DEBUG')
            vars['linkflags_64'].append('/DEBUG')

        # choose the runtime to link against
        # [/MD /MDd /MT /MTd]
        
        config['cxx'].update(vars)
        config['cc'].update(vars)

        defines = '_CRT_SECURE_NO_WARNINGS _FILE_OFFSET_BITS=64 _LARGEFILE_SOURCE WIN32 _USE_MATH_DEFINES NOMINMAX WIN32_LEAN_AND_MEAN'.split()
        flags = '/UUNICODE /U_UNICODE /EHs /GR'.split()
        threadFlags = '/D_REENTRANT'
        
        env.append_value('DEFINES', defines)
        env.append_value('CXXFLAGS', flags)
        env.append_value('CXXFLAGS_THREAD', threadFlags)
        
        env.append_value('CFLAGS', flags)
        env.append_value('CFLAGS_THREAD', threadFlags)
    
    else:
        self.fatal('OS/platform currently unsupported: %s' % sys_platform)
    
    #CXX
    if Options.options.warnings:
        env.append_value('CXXFLAGS', config['cxx'].get('warn', ''))
        env.append_value('CFLAGS', config['cc'].get('warn', ''))
    else:
        env.append_value('CXXFLAGS', config['cxx'].get('nowarn', ''))
        env.append_value('CFLAGS', config['cc'].get('nowarn', ''))
    if Options.options.verbose:
        env.append_value('CXXFLAGS', config['cxx'].get('verbose', ''))
        env.append_value('CFLAGS', config['cc'].get('verbose', ''))
    
    
    # We don't really use variants right now, so keep the default environment linked to the variant.
    variant = env
    if Options.options.debugging:
        variantName = '%s-debug' % sys_platform
        variant.append_value('CXXFLAGS', config['cxx'].get('debug', ''))
        variant.append_value('CFLAGS', config['cc'].get('debug', ''))
    else:
        variantName = '%s-release' % sys_platform
        optz = Options.options.with_optz
        variant.append_value('CXXFLAGS', config['cxx'].get('optz_%s' % optz, ''))
        variant.append_value('CFLAGS', config['cc'].get('optz_%s' % optz, ''))
    
    is64Bit = False
    #check if the system is 64-bit capable
    if re.match(winRegex, sys_platform):
        is64Bit = Options.options.enable64
    if not Options.options.enable32:
        #ifdef _WIN64
        if re.match(winRegex, sys_platform):
            frag64 = '''
#include <stdio.h>
int main() {
    #ifdef _WIN64
    printf("1");
    #else
    printf("0");
    #endif
    return 0; }
'''         
            output = self.check(fragment=frag64, define_ret=True,
                                execute=1, msg='Checking for 64-bit system')
            try:
                is64Bit = bool(int(output))
                if is64Bit:
                    self.msg('System size', '64-bit')
                else:
                    self.msg('System size', '32-bit')
            except:{}
        elif '64' in config['cxx']:
            if self.check_cxx(cxxflags=config['cxx']['64'], linkflags=config['cc'].get('linkflags_64', ''), mandatory=False):
                is64Bit = self.check_cc(cflags=config['cc']['64'], linkflags=config['cc'].get('linkflags_64', ''), mandatory=False)

    if is64Bit:
        if re.match(winRegex, sys_platform):
            variantName = variantName.replace('32', '64')
        else:
            variantName = '%s-64' % variantName
        variant.append_value('CXXFLAGS', config['cxx'].get('64', ''))
        variant.append_value('CFLAGS', config['cc'].get('64', ''))
        variant.append_value('LINKFLAGS', config['cc'].get('linkflags_64', ''))
    else:
        variant.append_value('CXXFLAGS', config['cxx'].get('32', ''))
        variant.append_value('CFLAGS', config['cc'].get('32', ''))
        variant.append_value('LINKFLAGS', config['cc'].get('linkflags_32', ''))

    env['IS64BIT'] = is64Bit
    self.all_envs[variantName] = variant
    self.setenv(variantName)
    
    env['VARIANT'] = variant['VARIANT'] = variantName

    #flag that we already detected
    self.env['DETECTED_BUILD_PY'] = True

@task_gen
@feature('untar')
def untar(tsk):
    untarDriver(tsk.path, tsk.fname)

def untarFile(path, fname):
    import tarfile
    f = path.find_or_declare(fname)
    tf = tarfile.open(f.abspath(), 'r')
    p = path.abspath()
    for x in tf:
        tf.extract(x, p)
    tf.close()

@task_gen
@feature('unzip')
def unzip(tsk):
    f = tsk.path.find_or_declare(tsk.fname)
    unzipper(f.abspath(), tsk.path.abspath())

# Needed to install files when using --target
@task_gen
@feature('install_tgt')
def install_tgt(tsk):
    if os.path.exists(tsk.dir.abspath()):
        if not hasattr(tsk, 'copy_to_source_dir') or not tsk.env['install_source']:
            tsk.copy_to_source_dir = False
        if not hasattr(tsk, 'pattern'):
            tsk.pattern = []
        if not hasattr(tsk, 'relative_trick'):
            tsk.relative_trick = False
        if isinstance(tsk.pattern, str):
            tsk.pattern = [tsk.pattern]
        for pattern in tsk.pattern:
            for file in tsk.dir.ant_glob(pattern):
                if tsk.relative_trick:
                    dest = tsk.install_path
                else:
                    dest = os.path.join(tsk.install_path, file.parent.path_from(tsk.dir))
                inst = tsk.bld.install_files(dest, file, 
                                      relative_trick=tsk.relative_trick)
                if inst and hasattr(tsk, 'chmod'):
                    inst.chmod = tsk.chmod

                if tsk.copy_to_source_dir:
                    dest = os.path.join('${PREFIX}', 'source')
                    inst2 = tsk.bld.install_files(dest, file, 
                                                  relative_trick=True)
                    if inst2 and hasattr(tsk, 'chmod'):
                        inst2.chmod = tsk.chmod
        if not hasattr(tsk, 'files'):
            tsk.files = []
        if isinstance(tsk.files, str):
            tsk.files = [tsk.files]
        for file in tsk.files:
            inst = tsk.bld.install_files(tsk.install_path, tsk.dir.make_node(file), 
                                  relative_trick=tsk.relative_trick)
            if inst and hasattr(tsk, 'chmod'):
                inst.chmod = tsk.chmod

            if tsk.copy_to_source_dir:
                dest = os.path.join('${PREFIX}', 'source')
                inst2 = tsk.bld.install_files(dest, tsk.dir.make_node(file), 
                                              relative_trick=True)
                if inst2 and hasattr(tsk, 'chmod'):
                    inst2.chmod = tsk.chmod

@task_gen
@feature('install_as_tgt')
def install_as_tgt(tsk):
    tsk.bld.install_as(tsk.install_as, tsk.file, cwd=tsk.dir)

@task_gen
@feature('symlink_as_tgt')
def symlink_as_tgt(tsk):
    tsk.bld.symlink_as(tsk.dest, tsk.src)

# Allows a target to specify additonal targets to be executed.
@task_gen
@feature('add_targets')
def add_targets(self):
    if isinstance(self.targets_to_add, str):
        self.targets_to_add = [self.targets_to_add]
    for target in self.targets_to_add:
        if isinstance(target, task_gen):
            target.post()
        else:
            self.bld.get_tgen_by_name(target).post()

# When building a DLL, don't install the implib.
@task_gen
@feature('no_implib')
@after('apply_implib')
def no_implib(tsk):
    if getattr(tsk, 'implib_install_task', None):
        tsk.implib_install_task.exec_task = Utils.nada

@task_gen
@feature('m4subst')
def m4subst(tsk):
    m4substFile(input=tsk.input, output=tsk.output, path=tsk.path, dict=tsk.dict, env=tsk.env, chmod=getattr(tsk, 'chmod', None))

def m4substFile(input, output, path, dict={}, env=None, chmod=None):
    import re
    #similar to the subst in misc.py - but outputs to the src directory
    m4_re = re.compile('@(\w+)@', re.M)

    infile = join(path.abspath(), input)
    outfile = join(path.abspath(), output)
    
    file = open(infile, 'r')
    code = file.read()
    file.close()

    # replace all % by %% to prevent errors by % signs in the input file while string formatting
    code = code.replace('%', '%%')

    s = m4_re.sub(r'%(\1)s', code)

    if not dict:
        names = m4_re.findall(code)
        for i in names:
            dict[i] = env.get_flat(i) or env.get_flat(i.upper())
    
    file = open(outfile, 'w')
    file.write(s % dict)
    file.close()
    if chmod: os.chmod(outfile, chmod)

@task_gen
@feature('handleDefs')
def handleDefs(tsk):
    handleDefsFile(input=tsk.input, output=tsk.output, path=tsk.path, defs=tsk.defs, chmod=getattr(tsk, 'chmod', None))

def handleDefsFile(input, output, path, defs, chmod=None):
    import re
    infile = join(path.abspath(), input)
    outfile = join(path.abspath(), output)
    
    file = open(infile, 'r')
    code = file.read()
    file.close()

    for k in defs.keys():
        v = defs[k]
        if v is None:
            v = ''
        code = re.sub(r'#undef %s(\n)' % k, r'#define %s %s\1' % (k,v), code)
    code = re.sub(r'(#undef[^\n]*)(\n)', r'/* \1 */\2', code)
    file = open(outfile, 'w')
    file.write(code)
    file.close()
    if chmod: os.chmod(outfile, chmod)

@task_gen
@feature('makeHeader')
def makeHeader(tsk):
    makeHeaderFile(output=tsk.output, path=tsk.path, defs=tsk.defs, undefs=getattr(tsk, 'undefs', None), chmod=getattr(tsk, 'chmod', None))
    
def makeHeaderFile(output, path, defs, undefs=None, chmod=None):
    outfile = join(path.abspath(), output)
    dest = open(outfile, 'w')
    guard = '__CONFIG_H__'
    dest.write('#ifndef %s\n#define %s\n\n' % (guard, guard))

    for k in defs.keys():
        v = defs[k]
        if v is None:
            v = ''
        dest.write('\n#ifndef %s\n#define %s %s\n#endif\n' % (k, k, v))
    
    if undefs:
        for u in undefs:
            dest.write('\n#undef %s\n' % u)

    dest.write('\n#endif /* %s */\n' % guard)
    dest.close()
    if chmod: os.chmod(outfile, chmod)

def getSolarisFlags(compilerName):
    # Newer Solaris compilers use -m32 and -m64, so check to see if these flags exist
    # If they don't, default to the old -xtarget flags
    # TODO: Is there a cleaner way to do this with check_cc() instead?
    bitFlag32 = '-xtarget=generic'
    bitFlag64 = '-xtarget=generic64'
    (out, err) = subprocess.Popen([compilerName, '-flags'], stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
            
    for line in out.split('\n'):
        if re.match(r'-m32.*', line):
            bitFlag32 = '-m32'
        elif re.match(r'-m64.*', line):
            bitFlag64 = '-m64'

    return (bitFlag32, bitFlag64)

def getWscriptTargets(bld, env, path):
    # Here we're taking a look at the current stack and adding on all the
    # wscript's that got us to this point.
    # The main additional difficulty here is that we can't just add these
    # pathnames on because then the same file will be marked to be installed by
    # multiple other targets (i.e. modules/c++/A and modules/c++/B will both
    # try to install modules/c++/wscript).  The way around this is to create
    # a named target for all these wscript's based on their full pathname.   
    wscriptTargets = []
    for item in inspect.stack():
        pathname = item[1]
        filename = os.path.basename(pathname)
        if filename in ['wscript', 'waf']:
            try:
                # If this succeeds, somebody else has already made this target
                # for us
                wscriptTargets.append(bld.get_tgen_by_name(pathname))
            except:
                # If we got here, no one has made the target yet, so we'll
                # make it
                # TODO: Not sure if there's a more efficient way to set
                #       dir below
                dirname = os.path.dirname(pathname)
                relpath = os.path.relpath(dirname, path.abspath())
                wscriptTargets.append(bld(features='install_tgt',
                                    target=pathname,
                                    pattern=['wscript', 'waf', '*.py', 'include/**/*', 'config.guess'],
                                    dir=path.make_node(relpath),
                                    install_path='${PREFIX}/source',
                                    relative_trick=True))
    return wscriptTargets

def addSourceTargets(bld, env, path, target):
    if env['install_source']:
        wscriptTargets = getWscriptTargets(bld, env, path)

        # We don't ever go into the project.cfg files, we call fromConfig on
        # them from a wscript, so we have to call these out separately.
        for targetName in path.ant_glob(['project.cfg']):
            try:
                wscriptTargets.append(bld.get_tgen_by_name(targetName))
            except:
                wscriptTargets.append(bld(features='install_tgt',
                                    target=targetName,
                                    files = 'project.cfg',
                                    pattern=['include/**/*'],
                                    dir=path, install_path='${PREFIX}/source',
                                    relative_trick=True))

        source = []
        for file in target.source:
            if type(file) is str:
                source.append(file)
            else:
                source.append(file.path_from(path))

        target.targets_to_add.append(bld(features='install_tgt',
                                         files = source,
                                         dir=path, install_path='${PREFIX}/source',
                                         relative_trick=True))

        target.targets_to_add += wscriptTargets

class SwitchContext(Context.Context):
    """
    Easily switch output directories without reconfiguration.
    """
    cmd='switch'
    def __init__(self,**kw):
        super(SwitchContext,self).__init__(**kw)
    def execute(self):
        out_lock = self.path.make_node(Options.options.out).make_node(Options.lockfile)
        root_lock = self.path.make_node(Options.lockfile)
        if exists(out_lock.abspath()):
            shutil.copy2(out_lock.abspath(), root_lock.abspath())
        else:
            raise Errors.WafError('Out directory "%s" not configured.'%Options.options.out)

class CPPBuildContext(BuildContext, CPPContext):
    pass
class CPPListContext(ListContext, CPPContext):
    pass
class CPPCleanContext(CleanContext, CPPContext):
    pass
class CPPInstallContext(InstallContext, CPPContext):
    pass

# VS config generator needs Python 2.5
if sys.version_info >= (2,5,0):
    from msvs import msvs_generator
    class CPPMSVSGenContext(msvs_generator, CPPContext):
        def __init__(self, **kw):
            self.waf_command = 'python waf'
            super(CPPMSVSGenContext, self).__init__(**kw)

