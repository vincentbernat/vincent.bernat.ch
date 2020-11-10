"""
CSS plugins
"""

import subprocess
from hyde.plugin import Plugin


class CSSPrefixerPlugin(Plugin):
    """Run CSS prefixer"""
    def text_resource_complete(self, resource, text):
        if resource.source_file.kind not in ("less", "css"):
            return
        mode = self.site.config.mode
        if mode == "development":
            print("HELLO")
            cleancss_options = "{format: 'beautify', level: 2}"
        else:
            cleancss_options = "{level: 2}"
        p = subprocess.Popen(
            ['nodejs', '-e', """
var autoprefixer = require('autoprefixer');
var postcss = require('postcss');
var CleanCSS = require('clean-css');
var input = '';

process.stdin.setEncoding('utf8')
process.stdin.on('readable', function() {
  var chunk = process.stdin.read();
  if (chunk) {
    input += chunk;
  }
});
process.stdin.on('end', function() {
  postcss([autoprefixer])
        .process(input, { from: undefined })
        .then(function(result) {
           process.stdout.write(
             new CleanCSS(%s).minify(result.css.toString()).styles
           );
        });
});
        """ % (cleancss_options,)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        stdout, _ = p.communicate(text.encode('utf-8'))
        assert p.returncode == 0
        return stdout.decode('utf-8')
