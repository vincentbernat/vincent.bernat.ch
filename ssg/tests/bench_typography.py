"""Benchmark for ssg.html.typography, on a test article."""

import statistics
import time
import unittest

import lxml.html

from ssg.html import typography

ARTICLES = 1000
RUNS = 5

ARTICLE = """
<html lang="en"><body><article>
<header><h1>A "test" article about route lookups</h1></header>
<div class="lf-text">
<p>In previous articles, I explained how the Linux kernel implements its
<a href="/en/blog/ipv4">IPv4 routing table</a>. It's a <em>compressed</em>
trie: "fast" lookups, a small memory footprint... The code is in
<code>net/ipv4/fib_trie.c</code> and the main function is
<code>fib_table_lookup()</code>. Everything started in the '90s with a
simple hash table.</p>
<p lang="fr">Dans les articles précédents, j'ai expliqué comment le noyau
Linux implémente sa table de routage. C'est un « arbre compressé » : les
recherches sont rapides ; l'empreinte mémoire est faible ! Avec 1 000 000 de
routes, il faut environ 120 Mo de mémoire et une recherche prend 50 ns sur
un lien à 10 Gbps. Est-ce suffisant ? Oui, dans 99 % des cas.</p>
<p>The French call this structure an <span lang="fr">arbre
préfixe</span><sup id="fnref:trie"><a href="#fn:trie">1</a></sup>. With
Linux 4.18, a lookup takes about 25 ns at a depth of 6, even with
500 000 routes. JavaScript developers on ThinkPads don't need to care: the
<strong>performance</strong> is "good enough" for everything except
high-frequency trading.</p>
<p lang="fr">Les anglophones parlent de <span lang="en">longest prefix
match</span> : la route la plus spécifique l'emporte. La fonction
<code>fib_lookup()</code> retourne le résultat dans une structure
<code>fib_result</code>. Depuis Linux 5.10, la consommation mémoire est
passée de 2,4 Gio à 1,8 Gio pour une table complète, soit une
amélioration de 25 %.</p>
<p>To conclude, the implementation is both compact and efficient. You can
reproduce these results with the scripts from the
<a href="https://github.com/example/repository">repository</a>. The
measurements were done at 2.4 GHz, with 16 GB of memory, and they are
consistent across kernel versions. That's all!</p>
</div>
</article></body></html>
"""


class BenchTypography(unittest.TestCase):
    def test_fix(self) -> None:
        times = []
        for _ in range(RUNS):
            roots = [lxml.html.fromstring(ARTICLE) for _ in range(ARTICLES)]
            start = time.perf_counter()
            for root in roots:
                typography.fix(root)
            times.append((time.perf_counter() - start) / ARTICLES * 1e6)
        print(
            f"typography: {statistics.median(times):.0f} µs/article "
            f"(min {min(times):.0f}, max {max(times):.0f})"
        )
