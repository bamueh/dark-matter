## Translating DNA to AA

You can translate DNA FASTA to amino acids in all six reading frames using
`dna-to-aa.py`. Start with this FASTA file:

    $ cat dna.fasta
    >SK7F6:25:89
    GTTACAATGAATG
    >SK7F6:30:80
    TCAGCCTCACCGCTGTGTCAAATGTACACAGATACTTTTCCGGCTCCAGCGCTGGCATGAAAACAAAATTAACAATTATTTTTTGA

On translating, you'll see what you'd expect:

    $ dna-to-aa.py < dna.fasta
    >SK7F6:25:89-frame0
    VTMNX
    >SK7F6:25:89-frame1
    LQ*M
    >SK7F6:25:89-frame2
    YNEX
    >SK7F6:25:89-frame0rc
    HSL*X
    >SK7F6:25:89-frame1rc
    IHCN
    >SK7F6:25:89-frame2rc
    FIVT
    >SK7F6:30:80-frame0
    SASPLCQMYTDTFPAPALA*KQN*QLFFX
    >SK7F6:30:80-frame1
    QPHRCVKCTQILFRLQRWHENKINNYFLX
    >SK7F6:30:80-frame2
    SLTAVSNVHRYFSGSSAGMKTKLTIIF*
    >SK7F6:30:80-frame0rc
    SKNNC*FCFHASAGAGKVSVYI*HSGEAX
    >SK7F6:30:80-frame1rc
    QKIIVNFVFMPALEPEKYLCTFDTAVRLX
    >SK7F6:30:80-frame2rc
    KK*LLILFSCQRWSRKSICVHLTQR*G*

There are 6 translations for each sequence.

You can see that `dna-to-aa.py` adds frame information to the read ids
(`rc` = reverse complement).

Any start (`M`) and stop (`*`) codons in the translations are left intact.

### Translating RNA

If your reads are RNA, you can pass the type using `--type rna`:

    $ dna-to-aa.py --type rna < dna-reads.fasta

### Requiring a sufficiently long ORF

To only output translations that contain at least one ORF of at least some
specified length:

    $ dna-to-aa.py --minORFLength 20 < dna.fasta
    >SK7F6:30:80-frame1
    QPHRCVKCTQILFRLQRWHENKINNYFLX
    >SK7F6:30:80-frame2
    SLTAVSNVHRYFSGSSAGMKTKLTIIF*
    >SK7F6:30:80-frame1rc
    QKIIVNFVFMPALEPEKYLCTFDTAVRLX

## Extracting ORFs

To find and extract all ORFs in the translations, use `extract-ORFs.py`:

    $ extract-ORFs.py < dna.fasta
    >SK7F6:25:89-frame0-[0:5)
    VTMNX
    >SK7F6:25:89-frame1-(0:2]
    LQ
    >SK7F6:25:89-frame2-(0:4)
    YNEX
    >SK7F6:25:89-frame0rc-(0:3]
    HSL
    >SK7F6:25:89-frame1rc-(0:4)
    IHCN
    >SK7F6:25:89-frame2rc-(0:4)
    FIVT
    >SK7F6:30:80-frame0-[0:19]
    SASPLCQMYTDTFPAPALA
    >SK7F6:30:80-frame1-(0:29)
    QPHRCVKCTQILFRLQRWHENKINNYFLX
    >SK7F6:30:80-frame2-[0:27]
    SLTAVSNVHRYFSGSSAGMKTKLTIIF
    >SK7F6:30:80-frame0rc-(0:5]
    SKNNC
    >SK7F6:30:80-frame1rc-[0:29)
    QKIIVNFVFMPALEPEKYLCTFDTAVRLX
    >SK7F6:30:80-frame2rc-(0:2]
    KK

This can also be restricted by minimal ORF length:

    $ extract-ORFs.py --minORFLength 20 < dna.fasta
    >SK7F6:30:80-frame1-(0:29)
    QPHRCVKCTQILFRLQRWHENKINNYFLX
    >SK7F6:30:80-frame2-[0:27]
    SLTAVSNVHRYFSGSSAGMKTKLTIIF
    >SK7F6:30:80-frame1rc-[0:29)
    QKIIVNFVFMPALEPEKYLCTFDTAVRLX

Unlike `dna-to-aa.py`, `extract-ORFs.py` writes one new sequence per ORF
and start and stop colons do not appear in the output.

`extract-ORFs.py` also adds a suffix to the read ids to indicate the ORF
offset in the original sequence, e.g., the `[0:29)` in
`SK7F6:30:80-frame1rc-[0:29)`.  A parenthesis indicates that that side of
the ORF was open (see below), whereas a square bracket indicates that the
ORF had a start or stop codon on that side. The numbers in between give the
start and stop offsets using Python's convention that the stop offset is
not part of the ORF.

To illustrate, the id `SK7F6:30:80-frame1rc-[0:29)` tells us that the
original read was `SK7F6:30:80` (`TCAGCCTCACCG...ATTATTTTTTGA`). That was
reverse complemented (`rc`) to get `TCAAAAAATAAT...CGGTGAGGCTGA`. The
translation was of the frame with offset 1: `CAAAAAATAAT...CGGTGAGGCTGA`,
producing ``. In that translation, the ORF had
Python offsets (0, 29), corresponding to the AA substring
`QKIIVNFVFMPALEPEKYLCTFDTAVRLX` (as shown above).

### Include "open" ORFs

Some reads start or end in the middle of an ORF. In this case, the ORF is
considered "open" on either the left or right (or both). It is not possible
to tell how long these ORFs actually are, we just have a minimum. If you'd
like these ORFs to be printed even though we do not know if they meet the
length requirement, use `--allowOpenORFs`:

    $ extract-ORFs.py  --minORFLength 20 --allowOpenORFs < dna.fasta
    >SK7F6:25:89-frame0-[0:5)
    VTMNX
    >SK7F6:25:89-frame1-(0:2]
    LQ
    >SK7F6:25:89-frame2-(0:4)
    YNEX
    >SK7F6:25:89-frame0rc-(0:3]
    HSL
    >SK7F6:25:89-frame1rc-(0:4)
    IHCN
    >SK7F6:25:89-frame2rc-(0:4)
    FIVT
    >SK7F6:30:80-frame1-(0:29)
    QPHRCVKCTQILFRLQRWHENKINNYFLX
    >SK7F6:30:80-frame2-[0:27]
    SLTAVSNVHRYFSGSSAGMKTKLTIIF
    >SK7F6:30:80-frame0rc-(0:5]
    SKNNC
    >SK7F6:30:80-frame1rc-[0:29)
    QKIIVNFVFMPALEPEKYLCTFDTAVRLX
    >SK7F6:30:80-frame2rc-(0:2]
    KK

### Starting from AA input

As well as accepting DNA FASTA, `extract-ORFs.py` can also handle AA FASTA
input, but you have to tell it. So if you already have a file of AA FASTA
and you want the ORFs, use `extract-ORFs.py --type aa`.

You'll probably never need to do this (because you can use
`extract-ORFs.py` to do the complete job), but you can convert DNA FASTA to
AA using `dna-to-aa.py` and pipe that into `extract-ORFs.py`:

    $ dna-to-aa.py < dna.fasta | extract-ORFs.py --minORFLength 20 --type aa
    >SK7F6:30:80-frame1-(0:29)
    QPHRCVKCTQILFRLQRWHENKINNYFLX
    >SK7F6:30:80-frame2-[0:27]
    SLTAVSNVHRYFSGSSAGMKTKLTIIF
    >SK7F6:30:80-frame1rc-[0:29)
    QKIIVNFVFMPALEPEKYLCTFDTAVRLX

In this case, if you forget to tell `extract-ORFs.py` that its input is AA,
you'll get a translation error and a reminder to use `--type aa`:

    $ dna-to-aa.py < dna.fasta | extract-ORFs.py
    Could not translate read 'SK7F6:25:89-frame0' sequence 'VTMNX' (Codon 'NXN' is invalid).
    Did you forget to run extract-ORFs.py with "--type aa"?
