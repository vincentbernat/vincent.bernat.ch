# -*- coding: utf-8 -*-
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
        p = subprocess.Popen(['nodejs', '-e', """
var autoprefixer = require('autoprefixer');
var postcss = require('postcss');
var input = '';

process.stdin.setEncoding('utf8')
process.stdin.on('readable', function() {
  var chunk = process.stdin.read();
  if (chunk) {
    input += chunk;
  }
});
process.stdin.on('end', function() {
  var output = postcss([autoprefixer]).process(input).css.toString();
  process.stdout.write(output);
});
        """], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        stdout, _ = p.communicate(text.encode('utf-8'))
        return stdout.decode('utf-8')
