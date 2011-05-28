# Should be sourced (by zsh)
(
    set -e
    autoload colors ; colors
    echo "${fg[green]} [+] Switch to master branch${fg[default]}"
    git checkout master
    echo "${fg[green]} [+] Regenerate all files${fg[default]}"
    rm -rf deploy
    hyde gen
    for file in deploy/media/js/*.js deploy/media/css/*.css ; do
	file=${file#deploy/media/}
	echo "${fg[green]} [+] MD5 hash for $file${fg[default]}"
	md5=$(md5sum deploy/media/${file} | cut -c1-8)
	newname=${file%.*}.${md5}.${file##*.}
	ln -s $(basename ${file}) deploy/media/${newname}
	sed -i "s+\([\"']\)/media/${file}\1+\1/media/${newname}\1+g" deploy/**/*.html
    done
    echo "${fg[green]} [+] Compare with current target${fg[default]}"
    rsync --exclude=.git -a --delete deploy/ .final/
    cd .final
    git add *
    git diff --stat HEAD
    echo -n "$fg[yellow] [?] More diff? ${fg[default]}"
    read answer
    case $answer in
	y*|Y*)
	    git diff --word-diff HEAD
	    ;;
    esac
    echo -n "$fg[yellow] [?] Publish? ${fg[default]}"
    read answer
    case $answer in
	y*|Y*)
	    echo "${fg[green]} [+] Commit changes${fg[default]}"
	    git commit -a -m "Autocommit"
	    cd ..
	    echo "${fg[green]} [+] Push to remote git repositories${fg[default]}"
	    git push github
	    git push ace.luffy.cx
	    echo "${fg[green]} [+] Sync!${fg[default]}"
	    rsync --exclude=.git -a .final/ ace.luffy.cx:/srv/www/luffy/
	    ;;
	*)
	    echo "${fg[yellow]} [+] Rollback${fg[default]}"
	    git reset --hard
	    git clean -d -f
	    ;;
    esac
)
