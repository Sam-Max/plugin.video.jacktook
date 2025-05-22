video_extensions = (
    '.001', '.3g2', '.3gp', '.asf', '.asx', '.avc', '.avi', '.avs', '.bdm', '.bdmv', '.bin', '.bivx', '.dat', '.divx',
    '.dv', '.dvr-ms', '.evo', '.f4v', '.fli', '.flv', '.h264', '.img', '.iso', '.m2t', '.m2ts', '.m2v', '.m3u8', '.m4v',
    '.mk3d', '.mkv', '.mov', '.mp4', '.mpeg', '.mpg', '.mpl', '.mpls', '.mts', '.nrg', '.nuv', '.ogm', '.ogv', '.pva',
    '.qt', '.rcv', '.rec', '.rmvb', '.sdp', '.svq3', '.tp', '.trp', '.ts', '.ty', '.udf', '.vc1', '.vdr', '.viv',
    '.vob', '.vp3', '.webm', '.wmv', '.xvid')

music_extensions = (
    '.aac', '.ac3', '.aif', '.aiff', '.ape', '.cmc', '.cmr', '.cue', '.dff', '.dmc', '.dsf', '.dsp', '.dts', '.dtshd',
    '.flac', '.gcm', '.gdm', '.idsp', '.imf', '.m15', '.m4a', '.m4b', '.mac', '.mka', '.mp+', '.mp2', '.mp3', '.mpa',
    '.mpc', '.mpdsp', '.mpp', '.mpt', '.mss', '.oga', '.ogg', '.opus', '.rma', '.rmt', '.rsd', '.sap', '.sfx', '.shn',
    '.spt', '.tak', '.tm2', '.tm8', '.tmc', '.tta', '.uni', '.waa', '.wam', '.wav', '.wma', '.wv', '.wvs', '.xwav')

picture_extensions = (
    '.apng', '.bmp', '.cbz', '.gif', '.ico', '.jp2', '.jpeg', '.jpg', '.pcx', '.png', '.tga', '.tif', '.tiff', '.webp')

subtitle_extensions = (
    '.aqt', '.ass', '.idx', '.jss', '.rt', '.smi', '.srt', '.ssa', '.sub', '.text', '.txt', '.utf', '.utf-8', '.utf8')

text_extensions = (
    '.ada', '.adb', '.ads', '.applescript', '.as', '.asc', '.ascii', '.ascx', '.asm', '.asmx', '.asp', '.aspx', '.atom',
    '.au3', '.awk', '.bas', '.bash', '.bashrc', '.bat', '.bbcolors', '.bcp', '.bdsgroup', '.bdsproj', '.bib',
    '.bowerrc', '.c', '.cbl', '.cc', '.cfc', '.cfg', '.cfm', '.cfml', '.cgi', '.clj', '.cljs', '.cls', '.cmake', '.cmd',
    '.cnf', '.cob', '.code-snippets', '.coffee', '.coffeekup', '.conf', '.cp', '.cpp', '.cpt', '.cpy', '.crt', '.cs',
    '.csh', '.cson', '.csproj', '.csr', '.css', '.csslintrc', '.csv', '.ctl', '.curlrc', '.cxx', '.d', '.dart', '.dfm',
    '.diff', '.dof', '.dpk', '.dpr', '.dproj', '.dtd', '.eco', '.editorconfig', '.ejs', '.el', '.elm', '.emacs', '.eml',
    '.ent', '.erb', '.erl', '.eslintignore', '.eslintrc', '.ex', '.exs', '.f', '.f03', '.f77', '.f90', '.f95', '.fish',
    '.for', '.fpp', '.frm', '.fs', '.fsproj', '.fsx', '.ftn', '.gemrc', '.gemspec', '.gitattributes', '.gitconfig',
    '.gitignore', '.gitkeep', '.gitmodules', '.go', '.gpp', '.gradle', '.groovy', '.groupproj', '.grunit', '.gtmpl',
    '.gvimrc', '.h', '.haml', '.hbs', '.hgignore', '.hh', '.hpp', '.hrl', '.hs', '.hta', '.htaccess', '.htc', '.htm',
    '.html', '.htpasswd', '.hxx', '.iced', '.iml', '.inc', '.inf', '.info', '.ini', '.ino', '.int', '.irbrc', '.itcl',
    '.itermcolors', '.itk', '.jade', '.java', '.jhtm', '.jhtml', '.js', '.jscsrc', '.jshintignore', '.jshintrc',
    '.json', '.json5', '.jsonld', '.jsp', '.jspx', '.jsx', '.ksh', '.less', '.lhs', '.lisp', '.log', '.ls', '.lsp',
    '.lua', '.m', '.m4', '.mak', '.map', '.markdown', '.master', '.md', '.mdown', '.mdwn', '.mdx', '.metadata', '.mht',
    '.mhtml', '.mjs', '.mk', '.mkd', '.mkdn', '.mkdown', '.ml', '.mli', '.mm', '.mxml', '.nfm', '.nfo', '.noon',
    '.npmignore', '.npmrc', '.nuspec', '.nvmrc', '.ops', '.pas', '.pasm', '.patch', '.pbxproj', '.pch', '.pem', '.pg',
    '.php', '.php3', '.php4', '.php5', '.phpt', '.phtml', '.pir', '.pl', '.pm', '.pmc', '.pod', '.pot', '.prettierrc',
    '.properties', '.props', '.pt', '.pug', '.purs', '.py', '.pyx', '.r', '.rake', '.rb', '.rbw', '.rc', '.rdoc',
    '.rdoc_options', '.resx', '.rexx', '.rhtml', '.rjs', '.rlib', '.ron', '.rs', '.rss', '.rst', '.rtf', '.rvmrc',
    '.rxml', '.s', '.sass', '.scala', '.scm', '.scss', '.seestyle', '.sh', '.shtml', '.sln', '.sls', '.spec', '.sql',
    '.sqlite', '.sqlproj', '.srt', '.ss', '.sss', '.st', '.strings', '.sty', '.styl', '.stylus', '.sub',
    '.sublime-build', '.sublime-commands', '.sublime-completions', '.sublime-keymap', '.sublime-macro', '.sublime-menu',
    '.sublime-project', '.sublime-settings', '.sublime-workspace', '.sv', '.svc', '.svg', '.swift', '.t', '.tcl',
    '.tcsh', '.terminal', '.tex', '.text', '.textile', '.tg', '.tk', '.tmlanguage', '.tmpl', '.tmtheme', '.tpl', '.ts',
    '.tsv', '.tsx', '.tt', '.tt2', '.ttml', '.twig', '.txt', '.v', '.vb', '.vbproj', '.vbs', '.vcproj', '.vcxproj',
    '.vh', '.vhd', '.vhdl', '.vim', '.viminfo', '.vimrc', '.vm', '.vue', '.webapp', '.webmanifest', '.wsc', '.x-php',
    '.xaml', '.xht', '.xhtml', '.xml', '.xs', '.xsd', '.xsl', '.xslt', '.y', '.yaml', '.yml', '.zsh', '.zshrc')


def _contains_extension(s, extensions):
    return s.lower().endswith(extensions)


def is_video(s):
    return _contains_extension(s, video_extensions)


def is_music(s):
    return _contains_extension(s, music_extensions)


def is_picture(s):
    return _contains_extension(s, picture_extensions)


def is_subtitle(s):
    return _contains_extension(s, subtitle_extensions)


def is_text(s):
    return _contains_extension(s, text_extensions)
