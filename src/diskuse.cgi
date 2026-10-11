#!/usr/bin/perl

=head1 DESCRIPTION

ディスク利用量表示CGI
2026/10/11 画面デザイン刷新（使用率メーター・機能別グラフ・ステータス表示・ダークモード/スマホ対応）(Neoreka)
2020/10/28 機能別容量表示及び取得日付表示追加
2014/10/08 容量集計ファイル.usage がない場合に「集計中」と表示するよう変更
2014/06/12 サービス別のデータ出力に対応
2013/09/06 リリース by t.shinobe

=head1 SYNOPSIS

CGIとして呼び出してください。

=cut

use strict;
use POSIX qw(strftime tzset);

# 表示タイムゾーン（顧客の地域に合わせる）
my $display_tz    = "UTC";
my $display_tz_lb = "UTC+0";

# 「上限に近い」表示を出す、閾値の何ポイント手前か
my $near_margin = 10;

# 契約情報ファイル
my $contract_file = "./contract/.data";

# 使用容量
my $usagefile = "./contract/.usage";

#　ヘッダ出力
print "Content-Type: text/html; charset=utf-8\n\n";

if ( !(-e $usagefile ) ) {
	nostatistics();
}

my ( $service_type, $ipaddr, $dn_usage_size, $dndb_usage_size, $url, $utime, $wmldata, $repfile, $docfile, $frmfile, $inffile, $schfile, $enqfile, $flwfile, $usrfile, $cdbfile ) = split(/\|/, readfile($usagefile));
chomp($utime);
$_ = ( defined $_ && /^\d+$/ ) ? $_ : 0 foreach ( $dn_usage_size, $dndb_usage_size, $utime, $wmldata, $repfile, $docfile, $frmfile, $inffile, $schfile, $enqfile, $flwfile, $usrfile, $cdbfile );
$ENV{TZ} = $display_tz;
tzset();
my $getdate = strftime("%d %b %Y, %H:%M", localtime($utime));

# 契約情報読み込み
my $str = readfile($contract_file);
chomp($str);
my ($company, $contract_diskusage, $threshold) = split(/\|/, $str);
$threshold = 90 if ( $threshold !~ /^\d+(\.\d+)?$/ );

# 容量計算（従来と同じ計算式：KB→GB、小数点以下2桁切り捨て）
my $total_kb      = $dn_usage_size + $dndb_usage_size;
my $p_total_usage = gb($total_kb);
my $percentage    = $contract_diskusage > 0 ? int( ( $total_kb / 1024 / 1024 ) / $contract_diskusage * 100 ) : 0;
my $p_remaining   = int( ( $contract_diskusage - $p_total_usage ) * 100 ) / 100;
$p_remaining = 0 if ( $p_remaining < 0 );

# ステータス判定（超過判定は従来と同じ）
my ( $status, $status_label, $status_note );
if ( $contract_diskusage / 100 * $threshold < $total_kb / 1024 / 1024 ) {
	( $status, $status_label ) = ( "critical", "Exceeded" );
	$status_note = "Usage is above the $threshold% alert threshold. Please delete unneeded files or contact us to increase your allocation.";
} elsif ( $percentage >= $threshold - $near_margin ) {
	( $status, $status_label ) = ( "warning", "Approaching limit" );
	$status_note = "Usage is close to the $threshold% alert threshold.";
} else {
	( $status, $status_label ) = ( "good", "Normal" );
	$status_note = "";
}

# 機能別容量（KB）
my @apps = (
	[ "Mail",                $wmldata ],
	[ "Schedule",            $schfile ],
	[ "Workflow",            $flwfile ],
	[ "Document Management", $docfile ],
	[ "Web Conference",      $frmfile ],
	[ "Questionnaire",       $enqfile ],
	[ "Circulation/Report",  $repfile ],
	[ "Information",         $inffile ],
	[ "Individual User",     $usrfile ],
	[ "AppSuite",            $cdbfile ],
);
my $apps_kb = 0;
$apps_kb += $_->[1] foreach (@apps);
my @rows = sort { $b->[1] <=> $a->[1] } grep { gb($_->[1]) > 0 } @apps;
my $other_kb = $dn_usage_size - $apps_kb;
my $other_row = ( gb($other_kb) > 0 ) ? [ "Database &amp; other data", $other_kb ] : undef;

my $meter_width = $percentage > 100 ? 100 : $percentage;
my $p_company   = esc($company);
my $p_alloc     = esc($contract_diskusage);
my $tick_left   = $threshold > 100 ? 100 : $threshold;

print << "EOL";
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Storage Usage</title>
<style>
:root {
  color-scheme: light;
  --page: #f4f4f2;
  --surface: #fcfcfb;
  --border: #e3e2de;
  --text-primary: #0b0b0b;
  --text-secondary: #52514e;
  --text-muted: #6f6e69;
  --accent: #2a78d6;
  --accent-track: #cde2fb;
  --other: #a3a29c;
  --good: #0ca30c;
  --warning: #fab219;
  --critical: #d03b3b;
  --good-bg: #e7f5e7;
  --warning-bg: #fdf3dc;
  --critical-bg: #fbe8e8;
}
\@media (prefers-color-scheme: dark) {
  :root {
    color-scheme: dark;
    --page: #111110;
    --surface: #1a1a19;
    --border: #2f2f2d;
    --text-primary: #ffffff;
    --text-secondary: #c3c2b7;
    --text-muted: #9a998f;
    --accent: #3987e5;
    --accent-track: #1f3550;
    --other: #6f6e69;
    --good-bg: #16301a;
    --warning-bg: #3a2f12;
    --critical-bg: #3a1a1a;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--page); color: var(--text-primary);
  font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", "Noto Sans Thai", sans-serif;
  -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 760px; margin: 0 auto; padding: 32px 16px 48px; }
header { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; flex-wrap: wrap; margin-bottom: 20px; }
.eyebrow { font-size: 13px; color: var(--text-muted); margin: 0 0 2px; }
h1 { font-size: 24px; font-weight: 600; margin: 0; letter-spacing: -0.01em; }
.updated { font-size: 13px; color: var(--text-muted); margin: 0; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 24px; margin-bottom: 16px; }
.card h2 { font-size: 15px; font-weight: 600; margin: 0 0 4px; }
.card .sub { font-size: 13px; color: var(--text-muted); margin: 0 0 18px; }
.headline { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.hero { font-size: 48px; font-weight: 600; line-height: 1.05; letter-spacing: -0.02em; }
.hero small { font-size: 18px; font-weight: 500; color: var(--text-secondary); letter-spacing: 0; }
.of { color: var(--text-secondary); margin-top: 6px; }
.badge { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px; font-size: 13px; font-weight: 600; white-space: nowrap; }
.badge svg { width: 14px; height: 14px; flex: none; }
.badge.good { background: var(--good-bg); color: var(--text-primary); }
.badge.good svg { color: var(--good); }
.badge.warning { background: var(--warning-bg); color: var(--text-primary); }
.badge.warning svg { color: var(--warning); }
.badge.critical { background: var(--critical-bg); color: var(--text-primary); }
.badge.critical svg { color: var(--critical); }
.meter { position: relative; height: 12px; border-radius: 6px; background: var(--accent-track); margin: 22px 0 8px; }
.meter .fill { height: 100%; border-radius: 6px; background: var(--accent); }
.meter.warning .fill { background: var(--warning); }
.meter.critical .fill { background: var(--critical); }
.meter .tick { position: absolute; top: -4px; bottom: -4px; width: 2px; background: var(--text-secondary); border-radius: 1px; }
.scale { display: flex; justify-content: space-between; font-size: 12px; color: var(--text-muted); }
.key { font-size: 12px; color: var(--text-muted); margin: 6px 0 0; }
.key-tick { display: inline-block; width: 2px; height: 12px; background: var(--text-secondary); border-radius: 1px; margin-right: 8px; vertical-align: -2px; }
.stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; background: var(--border); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; margin-top: 24px; }
.stat { background: var(--surface); padding: 12px 14px; }
.stat .label { font-size: 12px; color: var(--text-muted); }
.stat .value { font-size: 18px; font-weight: 600; }
.note { margin: 16px 0 0; font-size: 13px; color: var(--text-secondary); }
.rows { list-style: none; margin: 0; padding: 0; }
.row { display: grid; grid-template-columns: minmax(130px, 190px) 1fr 92px; align-items: center; gap: 14px; padding: 7px 8px; margin: 0 -8px; border-radius: 6px; }
.row:hover { background: var(--page); }
.row .name { font-size: 14px; }
.row .bar { height: 10px; position: relative; }
.row .bar span { display: block; height: 100%; min-width: 3px; border-radius: 0 4px 4px 0; background: var(--accent); }
.row.other .bar span { background: var(--other); }
.row .val { text-align: right; font-variant-numeric: tabular-nums; font-size: 14px; }
.row .val em { display: block; font-style: normal; font-size: 12px; color: var(--text-muted); }
.legend-other { display: inline-block; width: 10px; height: 10px; border-radius: 2px; background: var(--other); margin-right: 6px; vertical-align: -1px; }
.notes { font-size: 12px; color: var(--text-muted); margin: 8px 4px 0; padding-left: 18px; }
.notes li { margin: 2px 0; }
\@media (max-width: 560px) {
  .hero { font-size: 40px; }
  .stat { padding: 10px 10px; }
  .stat .value { font-size: 15px; }
  .card { padding: 20px 16px; }
  .row { grid-template-columns: 1fr 84px; row-gap: 4px; }
  .row .bar { grid-column: 1 / -1; grid-row: 2; }
}
\@media print {
  body { background: #fff; }
  .card { border-color: #ccc; break-inside: avoid; }
}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div>
    <p class="eyebrow">$p_company</p>
    <h1>Storage usage</h1>
  </div>
  <p class="updated">Last updated $getdate ($display_tz_lb)</p>
</header>

<section class="card" aria-labelledby="usage-title">
  <div class="headline">
    <div>
      <h2 id="usage-title" class="sub" style="margin:0 0 6px">Used storage</h2>
      <div class="hero">$p_total_usage <small>GB</small></div>
      <div class="of">of $p_alloc GB allocated &middot; $percentage%</div>
    </div>
EOL

print "    <span class=\"badge $status\" role=\"status\">" . icon($status) . "$status_label</span>\n";

print << "EOL";
  </div>
  <div class="meter $status" role="meter" aria-valuemin="0" aria-valuemax="100" aria-valuenow="$percentage" aria-label="Storage used: $percentage% of allocation">
    <div class="fill" style="width:$meter_width%"></div>
    <div class="tick" style="left:calc($tick_left% - 1px)" title="Alert threshold: $threshold%"></div>
  </div>
  <div class="scale"><span>0 GB</span><span>$p_alloc GB</span></div>
  <p class="key"><span class="key-tick" aria-hidden="true"></span>Alert threshold: $threshold% of allocation</p>
  <div class="stats">
    <div class="stat"><div class="label">Used</div><div class="value">$p_total_usage GB</div></div>
    <div class="stat"><div class="label">Remaining</div><div class="value">$p_remaining GB</div></div>
    <div class="stat"><div class="label">Allocated</div><div class="value">$p_alloc GB</div></div>
  </div>
EOL

if ( $status_note ne "" ) {
	print "  <p class=\"note\">$status_note</p>\n";
}

print "</section>\n";

if ( @rows or $other_row ) {
	print << "EOL";
<section class="card" aria-labelledby="apps-title">
  <h2 id="apps-title">Usage by app</h2>
  <p class="sub">Attached files per app, largest first. Share is of total used storage.</p>
  <ul class="rows">
EOL
	foreach my $r ( @rows ) {
		print approw( $r->[0], $r->[1], "" );
	}
	if ( $other_row ) {
		print approw( $other_row->[0], $other_row->[1], "other" );
	}
	print "  </ul>\n</section>\n";
}

print << "EOL";
<ul class="notes">
  <li>The status shows <strong>Exceeded</strong> when usage reaches the $threshold% alert threshold of your allocation.</li>
  <li>App figures are attached-file sizes (mail is the mailbox size). <span class="legend-other"></span>Database &amp; other data covers the database and system data not tied to a single app.</li>
  <li>Individual User includes Cabinet, ToDo and Notepad. Apps using less than 0.01 GB are not shown.</li>
  <li>Usage is measured once a day. 1 GB = 1,024 MB.</li>
</ul>
</div>
</body>
</html>
EOL

exit;

########################################################################
# 機能別の1行を出力
########################################################################
sub approw {
	my ( $name, $kb, $class ) = @_;
	my $g     = gb($kb);
	my $share = $total_kb > 0 ? $kb / $total_kb * 100 : 0;
	my $w     = sprintf("%.1f", $share);
	my $ps    = $share < 1 ? "&lt;1%" : sprintf("%d%%", $share + 0.5);
	my $cls   = $class ne "" ? "row $class" : "row";
	return "    <li class=\"$cls\" title=\"$name: $g GB ($ps of used storage)\"><span class=\"name\">$name</span><span class=\"bar\" aria-hidden=\"true\"><span style=\"width:$w%\"></span></span><span class=\"val\">$g GB<em>$ps</em></span></li>\n";
}

########################################################################
# ステータスアイコン
########################################################################
sub icon {
	my $s = shift;
	if ( $s eq "good" ) {
		return '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="8" cy="8" r="6.5"/><path d="M5 8.2l2 2 4-4.2"/></svg>';
	} elsif ( $s eq "warning" ) {
		return '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M8 1.8l6.6 12H1.4z" stroke-linejoin="round"/><path d="M8 6.3v3.4M8 11.8v.1"/></svg>';
	}
	return '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="8" cy="8" r="6.5"/><path d="M8 4.6v4.2M8 11.2v.1"/></svg>';
}

########################################################################
# KB→GB（小数点以下2桁切り捨て、従来と同じ）
########################################################################
sub gb {
	my $kb = shift;
	return int( $kb / 1024 / 1024 * 100 ) / 100;
}

########################################################################
# HTMLエスケープ
########################################################################
sub esc {
	my $s = shift;
	$s =~ s/&/&amp;/g; $s =~ s/</&lt;/g; $s =~ s/>/&gt;/g; $s =~ s/"/&quot;/g;
	return $s;
}

########################################################################
# ファイル読み込み
########################################################################
sub readfile {
	my $f = shift;
	open(my $fh, "<", $f) or return "";
	local $/;
	my $c = <$fh>;
	close($fh);
	return $c;
}

########################################################################
# 集計前の表示
########################################################################
sub nostatistics {
	print "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>Storage Usage</title></head>";
	print "<body style=\"margin:0;font:15px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;background:#f4f4f2;color:#0b0b0b\">";
	print "<div style=\"max-width:760px;margin:0 auto;padding:32px 16px\"><h1 style=\"font-size:24px;font-weight:600;margin:0 0 8px\">Storage usage</h1>";
	print "<p style=\"color:#52514e;margin:0\">Usage is being calculated. Please check back after the next daily update.</p></div></body></html>";
	exit;
}
