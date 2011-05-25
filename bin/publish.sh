# Should be sourced (by zsh)
(
    set -e
    autoload colors ; colors
    echo "${fg[green]} [+] Switch to master branch${fg[default]}"
    git checkout master
    echo "${fg[green]} [+] Regenerate all files${fg[default]}"
    rm -rf deploy
    hyde gen
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
	    rsync --exclude=.git -a --delete .final/ ace.luffy.cx:/srv/www/luffy/
	    ;;
	*)
	    echo "${fg[yellow]} [+] Rollback${fg[default]}"
	    git reset --hard
	    git clean -d -f
	    ;;
    esac
)
