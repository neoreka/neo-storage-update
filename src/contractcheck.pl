#!/usr/bin/perl

# Disk Usage check script desknet's on Cloud version 1.1.0
#
# 出力ファイル
# /var/www/html/contract/.usage
# /var/www/html/contract/.old
#
# 出力形式
# desknet'sタイプ|IP|利用容量|URL|update unix time
#
# Tadahira Shinobe(shinobe@net-ing.com), NET-ING Co., LTD. 2013/7/25
#
# 2026/10/11 稼働中PostgreSQLのデータディレクトリ(-D)を自動検出して集計 (Neoreka)
# 2024/10/24 PostgreSQL16対応
# 2021/09/22 PostgreSQL13対応
# 2020/10/28 AWS環境における共通化及び機能別使用量の取得機能追加
# 2013/7/31 すべてのタイプをサポート
# 2013/7/25 desket's NEO/DBをサポート
# 2017/10/28 PostrgeSQL9.6向けにクラスタパス
# 2020/06/11 7日間のデータを残すことになる
#

use strict;
use Socket;

# 契約情報ファイル
my $contract_file = "/var/www/html/contract/.data";
my ($company,$contract_size,$threshold) = split(/\|/, `cat $contract_file`);
chomp($threshold);

# GB -> KBに変換
$contract_size = $contract_size * 1024 * 1024;

# 使用容量
my $usagefile = "/var/www/html/contract/.usage";
my $old = "";
my $wmldata = 0;
my $repfile = 0;
my $docfile = 0;
my $frmfile = 0;
my $inffile = 0;
my $schfile = 0;
my $enqfile = 0;
my $flwfile = 0;
my $usrfile = 0;
my $cdbfile = 0;

# 集計ディレクトリリスト
my %dirlist = (
	'neo1' => [
		'/var/lib/pgsql96/data',
		'/var/www/cgi-bin/dneo/data',
		'/var/www/cgi-bin/dneo/file',
		'/var/www/cgi-bin/dneo/wmldata',
		'/var/www/cgi-bin/dndb/wddata'
		],
	'neo2' => [
		'/var/lib/pgsql13/data',
		'/var/www/cgi-bin/dneo/data',
		'/var/www/cgi-bin/dneo/file',
		'/var/www/cgi-bin/dneo/wmldata',
		'/var/www/cgi-bin/dndb/wddata'
		],
	'neo3' => [
		'/var/lib/pgsql16/data',
		'/var/www/cgi-bin/dneo/data',
		'/var/www/cgi-bin/dneo/file',
		'/var/www/cgi-bin/dneo/wmldata',
		'/var/www/cgi-bin/dndb/wddata'
		],
	'ent' => [
		'/var/lib/pgsql/data',
		'/var/www/cgi-bin/dnet/data',
		'/var/www/cgi-bin/dnet/file'
		],
	'std' => [
		'/var/www/cgi-bin/dnet/data',
		'/var/www/cgi-bin/dnet/file'
		]
);

# ホスト名取得
my $host = `hostname`;
chomp($host);
$host = substr($host,4);

# IPアドレス取得
my $ipaddr = join('.', unpack("C*", gethostbyname($host)));

# 時刻取得
my $utime = time();

# 利用バージョンの取得
my $dntype = &gettype;

# 集計対象ディレクトリ
# 稼働中のPostgreSQLのデータディレクトリが取得できた場合は、固定パスの代わりにそれを使う
my @dirs = @{$dirlist{$dntype}};
if ( $dntype ne 'std' ) {
	my $pgdata = &getpgdata;
	if ( $pgdata ne "" ) {
		@dirs = grep { !/pgsql/ } @dirs;
		unshift(@dirs, $pgdata);
	}
}

# 容量計算
my $usage_size = 0;
foreach(@dirs) {
	if ( -e $_ ) {

		my $tmp = `/usr/bin/du -skL $_ | cut -f1`;
		chomp($tmp);
		if ( $_ =~ /wmldata/ ) {
			$wmldata = $tmp;
		}
		$usage_size += $tmp;
	}
}

if ( $dntype =~ /neo/ ) {
	########
	# 機能別データ容量取得
	########
	$repfile = dirsize("/var/www/cgi-bin/dneo/file/1/creport");
	$docfile = dirsize("/var/www/cgi-bin/dneo/file/1/doc");
	$frmfile = dirsize("/var/www/cgi-bin/dneo/file/1/forum");
	$inffile = dirsize("/var/www/cgi-bin/dneo/file/1/information");
	$schfile = dirsize("/var/www/cgi-bin/dneo/file/1/schedule");
	$enqfile = dirsize("/var/www/cgi-bin/dneo/file/1/xenquete");
	$flwfile = dirsize("/var/www/cgi-bin/dneo/file/1/xflow");
	$usrfile = dirsize("/var/www/cgi-bin/dneo/file/1/user");
	$cdbfile = dirsize("/var/www/cgi-bin/dneo/file/1/cdb");
	chop($dntype);
}

if (open(FH,">$usagefile")) {
#	print FH "$dntype|$ipaddr|$usage_size|http://$host/contract/index.cgi|$utime";
	print FH "$dntype|$ipaddr|$usage_size||http://$host/contract/index.cgi|$utime|$wmldata|$repfile|$docfile|$frmfile|$inffile|$schfile|$enqfile|$flwfile|$usrfile|$cdbfile";
	close(FH);
} else {
}

if ( -e "/var/www/html/contract/.old") {
	$old = `tail -6 /var/www/html/contract/.old`;
        open(FH,">/var/www/html/contract/.old");
        print FH "$old\n$usage_size";
        close(FH);
} else {
        open(FH,">/var/www/html/contract/.old");
        print FH "$usage_size";
       close(FH);
}

exit;

sub gettype {
	if ( -d "/var/www/cgi-bin/dneo" ) {
		my $utype='neo2';
		if ( -e "/var/www/cgi-bin/dneo/data/app" ) {
		        open(FH, "/var/www/cgi-bin/dneo/data/app");
		        my @lines = <FH>;
		        close(FH);
        		foreach ( @lines ) {
		               	if ( /port=5432/ ) {
                       			$utype='neo3';
		               	}
			}
		}
		return $utype;
	} elsif ( -e "/var/www/cgi-bin/dnet/data/app" ) {
		return 'ent';
	} else {
		return 'std';
	}
}

########################################################################
# 稼働中のPostgreSQLのデータディレクトリ(-D)を取得
# 取得できない場合は空文字を返す(従来の固定パスで集計)
########################################################################

sub getpgdata {
	foreach ( `/usr/bin/ps -C postgres,postmaster -o args=` ) {
		if ( /^\S*(?:postgres|postmaster)\s.*-D\s*(\/\S+)/ ) {
			my $path = $1;
			if ( -d $path ) {
				return $path;
			}
		}
	}
	return "";
}

########################################################################
# ディレクトリサイズの集計
########################################################################

sub dirsize {
        my $path = shift;
        if ( -d $path ) {
                my $str = `/usr/bin/du -sk $path`;
                chomp($str);
                if ( $str =~ /^([0-9]+)/ ) {
                        return $1;
                }
        }
        return 0;
}

