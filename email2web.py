#!/usr/bin/env python3
"""
Take an HTML message, extract the images and html into separate file that can 
be handled by a web browser.

Can be run from within a mailer like mutt, or independently
on a single message file:

Usage: email2web <file0> [<file1> ...]

This originally started as a modification to Akkana Peck's viewhtmlemail [1], 
but ended up as a complete rewrite.

[1]: https://github.com/akkana/scripts/blob/master/viewhtmlmail

To use it from mutt, put the following lines in your .muttrc:
macro index <F10> "<pipe-message>~/bin/viewhtmlmail\n" "View HTML in browser"
macro pager <F10> "<pipe-message>~/bin/viewhtmlmail\n" "View HTML in browser"
"""

import os
import sys
import re
# import time
# import shutil
import email
import mimetypes
import tempfile
import subprocess


def find_first_maildir_file(maildir):
    '''Maildir: inside /tmp/mutttmpbox, mutt creates another level of
       directory, so the file will be something like /tmp/mutttmpbox/cur/1.
       So recurse into directories until we find an actual mail file.
       Return a full path to the filename.
    '''
    for root, _, files in os.walk(maildir):
        for file in files:
            if not file.startswith('.'):
                return os.path.join(root, file)
    return None


def email2web(file, tmpdir):
    """Function to convert an email, `file`, into a web directory,
    i.e. to extract embedded images to the `tmpdir` directory."""
    if file:
        if os.path.isdir(file):
            # Maildir: f is a maildir like /tmp/mutttmpbox,
            # and inside it, for some reason, mutt creates another
            # level of directory named either cur or new
            # depending on whether the message is already marked read.
            # So we have to open the first file inside either cur or new.
            # In case mutt changes this behavior, let's take the first
            # non-dotfile inside the first non-dot directory.
            msg = None
            for maildir in os.listdir(f):
                with open(find_first_maildir_file(f)) as fp:
                    msg = email.message_from_string(fp.read())
                    break
        else:
            # Mbox format: we assume there's only one message in the mbox.
            with open(f) as fp:
                msg = email.message_from_string(fp.read())
    else:
        msg = email.message_from_string(sys.stdin.read())

    html_part = None
    counter = 1
    subfiles = []
    filenames = set()
    for part in msg.walk():

        # print ""

        # part has, for example:
        # items: [('Content-Type', 'image/jpeg'), ('Content-Transfer-Encoding', 'base64'), ('Content-ID', '<14.3631871432@web82503.mail.mud.yahoo.com>'), ('Content-Disposition', 'attachment; filename="ATT0001414.jpg"')]
        # keys: ['Content-Type', 'Content-Transfer-Encoding', 'Content-ID', 'Content-Disposition']
        # values: ['image/jpeg', 'base64', '<14.3631871432@web82503.mail.mud.yahoo.com>', 'attachment; filename="ATT0001414.jpg"']

        # multipart/* are just containers
        #if part.get_content_maintype() == 'multipart':
        if part.is_multipart() or part.get_content_type == 'message/rfc822':
            continue

        if part.get_content_subtype() == 'html':
            if html_part:
                print("Eek, more than one html part!")
            html_part = part

        # Save it to a file in the temp dir.
        filename = part.get_filename()
        if not filename:
            print("No filename; making one up")
            ext = mimetypes.guess_extension(part.get_content_type())
            if not ext:
                # Use a generic bag-of-bits extension
                ext = '.bin'
            filename = 'part-%03d%s' % (counter, ext)

        # Applications should really sanitize the given filename so that an
        # email message can't be used to overwrite important files.
        # As a first step, guard against ../
        if '../' in filename:
            print("Eek! Possible security problem in filename %s" % filename)
            continue

        # Some mailers, apparently including gmail, will attach multiple
        # images to the same mail all with the same name, like "image.png".
        # So check whether we have to uniquify the names.

        if filename in filenames:
            orig_basename, orig_ext = os.path.splitext(filename)
            counter = 0
            while filename in filenames:
                counter += 1
                filename = "%s-%d%s" % (orig_basename, counter, orig_ext)
        filenames.add(filename)
        filename = os.path.join(tmpdir, filename)

        # print "%10s %5s %s" % (part.get_content_type(), ext, filename)

        # Mailers may use Content-Id or Content-ID (or, presumably, various
        # other capitalizations). So we can't just look it up simply.
        content_id = None
        for k in list(part.keys()):
            if k.lower() == 'content-id':
                # Remove angle brackets, if present.
                # part['Content-Id'] is unmutable -- attempts to change it
                # are just ignored -- so copy it to a local mutable string.
                content_id = part[k]
                if content_id.startswith('<') and content_id.endswith('>'):
                    content_id = content_id[1:-1]

                subfiles.append({'filename': filename,
                                 'Content-Id': content_id})
                counter += 1
                fp = open(filename, 'wb')
                fp.write(part.get_payload(decode=True))
                # print "wrote", os.path.join(tmpdir, filename)
                fp.close()
                break     # no need to look at other keys

        if not content_id:
            print("%s doesn't have a Content-Id, not saving" % filename)
            # print("keys: %s" % str(part.keys()))

    # for sf in subfiles:
    #     print sf

    # We're done saving the parts. It's time to save the HTML part.
    htmlfile = os.path.join(tmpdir, "viewhtml.html")
    fp = open(htmlfile, 'wb')
    htmlsrc = html_part.get_payload(decode=True)

    # Substitute all the filenames for CIDs:
    for sf in subfiles:
        # Yes, yes, I know:
        # https://stackoverflow.com/questions/1732348/regex-match-open-tags-except-xhtml-self-contained-tags/
        # but eventually this script will be integrated with viewmailattachments
        # (which uses BeautifulSoup) and that problem will go away.
        htmlsrc = re.sub('cid: ?' + sf['Content-Id'],
                         'file://' + sf['filename'],
                         htmlsrc, flags=re.IGNORECASE)

    fp.write(htmlsrc)
    fp.close()

    # Now we have the file. Call a browser on it.
    browser = os.environ["BROWSER"]
    if not browser:
        browser = "firefox"
    print("%s file://%s" % (browser, htmlfile))
    subprocess.call([browser, "file://%s" % htmlfile])

def main(argv):
    """This is the main function"""
    tmpdir = tempfile.mkdtemp()
    for filename in argv[1:]:
        try:
            email2web(filename, tmpdir)
        except Exception as e:
            print(e, file=sys.stderr)
            return -1
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
