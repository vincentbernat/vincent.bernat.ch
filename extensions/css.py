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
var mqpacker = require('css-mqpacker');
var cssnano = require('cssnano');
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
  postcss([autoprefixer, mqpacker, cssnano({reduceIdents: false, reduceInitial: false})])
        .process(input, { from: undefined })
        .then(function(result) {
          process.stdout.write(result.css.toString());
        });
});
        """], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        stdout, _ = p.communicate(text.encode('utf-8'))
        assert p.returncode == 0
        return stdout.decode('utf-8')
