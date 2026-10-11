#!/usr/bin/perl
#
# 容量集計管理CGI ver 2.00
#
# 2026/10/11 ver 2.00 管理者向け画面デザイン刷新（使用状況・7日間推移・ダークモード/スマホ対応）(Neoreka)
#                     ※アラート閾値・契約種別は画面から外し、保存時は現在の値を引き継ぐ
#                     ※保存処理・保存条件は従来と同じ
# 2021/03/23 ver 1.40 AWS用に残契約容量を追加
# 2020/06/10 ver 1.30 AWS用に物理ディスク容量のチェック処理を追加
# 2016/06/17 ver 1.20 7日分の容量データを保存するよう設定
# 2014/6/12 ver 1.10 サービス別のデータ出力に対応
# 2013/9/6 ver 1.00 リリース by t.shinobe

use strict;
use CGI;
use POSIX qw(strftime tzset);

# 表示タイムゾーン
my $display_tz    = "UTC";
my $display_tz_lb = "UTC+0";

# 「上限に近い」表示を出す、閾値の何ポイント手前か
my $near_margin = 10;

# 顧客向け画面
my $customer_page = "../diskuse.cgi";

my $q = new CGI;

# POSTされたパラメータの読み込み
my $mode                = $q->param('mode');
my $post_company        = $q->param('company');
my $post_disk           = $q->param('disk');
my $post_threshold      = $q->param('threshold');
my $post_contract_type  = $q->param('contract_type');

# ホスト名（表示用）
my $domain = $ENV{'HTTP_HOST'} || $ENV{'SERVER_NAME'} || `hostname`;
chomp($domain);

# 契約情報ファイル
my $contract_file = "./.data";

# 使用容量
my $usagefile = "./.usage";
my ( $service_type, $ipaddr, $dn_usage_size, $dndb_usage_size, $url, $utime ) = split(/\|/, readfile($usagefile));
chomp($utime);
$_ = ( defined $_ && /^\d+$/ ) ? $_ : 0 foreach ( $dn_usage_size, $dndb_usage_size, $utime );
$ENV{TZ} = $display_tz;
tzset();
my $getdate = $utime > 0 ? strftime("%d %b %Y, %H:%M", localtime($utime)) : "not yet measured";

# 過去の容量(dnのみ)
my $oldfile = "./.old";
my @olddata = grep { /^\d+$/ } split(/\n/, readfile($oldfile));

# サービスタイプを表示用に修正
my @types;
push(@types, "desknet's NEO")      if ( $service_type =~ /neo/ );
push(@types, "desknet's Standard") if ( $service_type =~ /std/ );
push(@types, "desknet's DB")       if ( $service_type =~ /dndb/ );
my $p_service_type = @types ? join(", ", @types) : "Unknown";

# 契約情報変更の場合、契約情報ファイルを更新（保存条件は従来と同じ）
# 画面に無い項目（アラート閾値・契約種別）は、送信されなければ現在の値を引き継ぐ
my $save_result = "";
if ( defined $mode && $mode eq 'change' ) {
	if ( $post_disk =~ /^([\d\.]+)$/ ) {
		my $cur = readfile($contract_file);
		chomp($cur);
		my ( undef, undef, $cur_threshold, $cur_contract_type ) = split(/\|/, $cur);
		$post_threshold     = $cur_threshold     if ( !defined $post_threshold );
		$post_contract_type = $cur_contract_type if ( !defined $post_contract_type );
		open(FH, ">$contract_file");
		print FH "$post_company|$post_disk|$post_threshold|$post_contract_type\n";
		close(FH);
		$save_result = "saved";
	} else {
		$save_result = "notsaved";
	}
}

#　ヘッダ出力
print "Content-Type: text/html; charset=utf-8\n\n";

# 契約情報読み込み
my $str = readfile($contract_file);
chomp($str);
my ($company, $contract_diskusage, $threshold, $contract_type) = split(/\|/, $str);
my $alloc_num = ( $contract_diskusage =~ /^[\d\.]+$/ && $contract_diskusage > 0 ) ? $contract_diskusage : 0;
my $thr_num   = ( $threshold =~ /^\d+(\.\d+)?$/ ) ? $threshold : 0;

# 容量計算（従来と同じ計算式：KB→GB、小数点以下2桁切り捨て）
my $total_kb      = $dn_usage_size + $dndb_usage_size;
my $p_total_usage = gb($total_kb);
my $percentage    = $alloc_num > 0 ? int( ( $total_kb / 1024 / 1024 ) / $alloc_num * 100 ) : 0;
my $remaining     = int( ( $alloc_num - $p_total_usage ) * 100 ) / 100;

# 使用状況ステータス（超過判定は従来と同じ）
my ( $status, $status_label );
if ( $alloc_num > 0 && $alloc_num / 100 * $thr_num < $total_kb / 1024 / 1024 ) {
	( $status, $status_label ) = ( "critical", "Exceeded" );
} elsif ( $alloc_num > 0 && $percentage >= $thr_num - $near_margin ) {
	( $status, $status_label ) = ( "warning", "Approaching limit" );
} else {
	( $status, $status_label ) = ( "good", "Normal" );
}

my $meter_width = $percentage > 100 ? 100 : $percentage;
$remaining = 0 if ( $remaining < 0 );

my $p_company = esc($company);
my $p_alloc   = esc($contract_diskusage);
my $p_domain  = esc($domain);

print << "EOL";
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Admin: Contract Settings</title>
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
  --admin-bar: #1f2430;
  --admin-text: #ffffff;
  --admin-muted: #b9bfcc;
  --field-bg: #ffffff;
  --field-border: #c9c8c2;
  --good: #0ca30c;
  --warning: #fab219;
  --critical: #d03b3b;
  --good-bg: #e7f5e7;
  --warning-bg: #fdf3dc;
  --critical-bg: #fbe8e8;
  --focus: #2a78d6;
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
    --admin-bar: #0b0d12;
    --admin-muted: #9aa1b0;
    --field-bg: #121211;
    --field-border: #3d3d3a;
    --good-bg: #16301a;
    --warning-bg: #3a2f12;
    --critical-bg: #3a1a1a;
    --focus: #3987e5;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--page); color: var(--text-primary);
  font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif;
  -webkit-font-smoothing: antialiased;
}
.adminbar { background: var(--admin-bar); color: var(--admin-text); }
.adminbar .in { max-width: 960px; margin: 0 auto; padding: 12px 16px; display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.adminbar .brand { display: flex; align-items: center; gap: 10px; font-weight: 600; font-size: 14px; }
.adminbar .brand svg { width: 18px; height: 18px; }
.adminbar .tag { font-size: 11px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; border: 1px solid var(--admin-muted); color: var(--admin-text); border-radius: 4px; padding: 1px 6px; }
.adminbar .host { font-size: 13px; color: var(--admin-muted); }
.adminbar a { color: var(--admin-text); font-size: 13px; text-decoration: none; border-bottom: 1px solid var(--admin-muted); }
.adminbar a:hover { border-bottom-color: var(--admin-text); }
.wrap { max-width: 960px; margin: 0 auto; padding: 24px 16px 48px; }
.page-head { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; flex-wrap: wrap; margin-bottom: 16px; }
h1 { font-size: 24px; font-weight: 600; margin: 0; letter-spacing: -0.01em; }
.page-head p { margin: 2px 0 0; color: var(--text-muted); font-size: 13px; }
.alert { display: flex; gap: 10px; align-items: flex-start; border-radius: 10px; padding: 12px 14px; margin-bottom: 16px; font-size: 14px; border: 1px solid transparent; }
.alert svg { width: 18px; height: 18px; flex: none; margin-top: 1px; }
.alert.warning { background: var(--warning-bg); border-color: var(--warning); }
.alert.warning svg { color: var(--warning); }
.alert.good { background: var(--good-bg); border-color: var(--good); }
.alert.good svg { color: var(--good); }
.alert.critical { background: var(--critical-bg); border-color: var(--critical); }
.alert.critical svg { color: var(--critical); }
.alert strong { font-weight: 600; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 22px; }
.card.span { grid-column: 1 / -1; }
.card h2 { font-size: 15px; font-weight: 600; margin: 0 0 4px; display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.card .sub { font-size: 13px; color: var(--text-muted); margin: 0 0 16px; }
.hero { font-size: 40px; font-weight: 600; line-height: 1.1; letter-spacing: -0.02em; margin-top: 8px; }
.hero small { font-size: 16px; font-weight: 500; color: var(--text-secondary); letter-spacing: 0; }
.of { color: var(--text-secondary); font-size: 14px; }
.badge { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; white-space: nowrap; color: var(--text-primary); }
.badge svg { width: 14px; height: 14px; flex: none; }
.badge.good { background: var(--good-bg); } .badge.good svg { color: var(--good); }
.badge.warning { background: var(--warning-bg); } .badge.warning svg { color: var(--warning); }
.badge.critical { background: var(--critical-bg); } .badge.critical svg { color: var(--critical); }
.meter { position: relative; height: 10px; border-radius: 5px; background: var(--accent-track); margin: 16px 0 6px; }
.meter .fill { height: 100%; border-radius: 5px; background: var(--accent); }
.meter.warning .fill { background: var(--warning); }
.meter.critical .fill { background: var(--critical); }
.scale { display: flex; justify-content: space-between; font-size: 12px; color: var(--text-muted); }
dl.kv { max-width: 360px; display: grid; grid-template-columns: auto 1fr; gap: 6px 16px; margin: 16px 0 0; font-size: 14px; }
dl.kv dt { color: var(--text-muted); }
dl.kv dd { margin: 0; text-align: right; font-variant-numeric: tabular-nums; }
form .field { margin-bottom: 16px; }
form label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 6px; }
form .hint { font-size: 12px; color: var(--text-muted); margin-top: 4px; }
.fields { display: grid; grid-template-columns: 2fr 1fr; gap: 0 16px; max-width: 640px; }
.inputwrap { display: flex; align-items: center; background: var(--field-bg); border: 1px solid var(--field-border); border-radius: 8px; }
.inputwrap:focus-within { outline: 2px solid var(--focus); outline-offset: 1px; }
.inputwrap input, .inputwrap select { flex: 1; min-width: 0; border: 0; background: transparent; color: var(--text-primary); font: inherit; padding: 9px 11px; outline: none; }
.inputwrap .unit { padding: 0 11px 0 0; color: var(--text-muted); font-size: 14px; }
.actions { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; border-top: 1px solid var(--border); padding-top: 16px; }
button { font: inherit; font-weight: 600; font-size: 14px; color: #fff; background: var(--accent); border: 0; border-radius: 8px; padding: 9px 18px; cursor: pointer; }
button:hover { filter: brightness(1.08); }
button:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
.actions .hint { font-size: 12px; color: var(--text-muted); }
.chart { width: 100%; height: auto; display: block; max-height: 220px; }
.chart .bar { fill: var(--accent); }
.chart .bar.today { fill: var(--accent); }
.chart .bar.past { fill: var(--accent); opacity: .55; }
.chart .grid { stroke: var(--border); stroke-width: 1; }
.chart text { fill: var(--text-muted); font-size: 11px; }
.chart text.v { fill: var(--text-secondary); font-size: 11px; }
.chart .hit:hover + .bar, .chart g:hover .bar { opacity: 1; }
table.hist { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 12px; }
table.hist th, table.hist td { padding: 6px 8px; border-bottom: 1px solid var(--border); }
table.hist th { text-align: left; font-weight: 500; color: var(--text-muted); }
table.hist td { text-align: right; font-variant-numeric: tabular-nums; }
details { margin-top: 8px; }
summary { cursor: pointer; font-size: 13px; color: var(--text-secondary); }
footer { margin-top: 24px; font-size: 12px; color: var(--text-muted); }
\@media (max-width: 760px) {
  .grid { grid-template-columns: 1fr; }
}
\@media (max-width: 420px) {
  .fields { grid-template-columns: 1fr; }
}
</style>
</head>
<body>
<div class="adminbar"><div class="in">
  <div class="brand">
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M8 1.5l5.5 2v4.2c0 3.3-2.3 5.9-5.5 6.8-3.2-.9-5.5-3.5-5.5-6.8V3.5z"/><path d="M5.6 8l1.7 1.7 3.1-3.2"/></svg>
    <span>Administrator</span><span class="tag">Admin only</span>
    <span class="host">$p_domain</span>
  </div>
  <a href="$customer_page" target="_blank" rel="noopener">View customer page &#8599;</a>
</div></div>

<div class="wrap">
<div class="page-head">
  <div>
    <h1>Contract settings</h1>
    <p>$p_company &middot; $p_service_type</p>
  </div>
  <p>Usage measured $getdate ($display_tz_lb)</p>
</div>

<div class="alert warning" role="note">
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M8 1.8l6.6 12H1.4z" stroke-linejoin="round"/><path d="M8 6.3v3.4M8 11.8v.1"/></svg>
  <div><strong>Only for internal use.</strong> Do not share this page with customers.</div>
</div>
EOL

if ( $save_result eq "saved" ) {
	print "<div class=\"alert good\" role=\"status\">" . icon("good") . "<div><strong>Settings saved.</strong> The customer page uses the new values immediately.</div></div>\n";
} elsif ( $save_result eq "notsaved" ) {
	print "<div class=\"alert critical\" role=\"alert\">" . icon("critical") . "<div><strong>Not saved.</strong> Allocated size must be a number (for example 50 or 12.5).</div></div>\n";
}

print << "EOL";
<div class="grid">

<section class="card span" aria-labelledby="set-title">
  <h2 id="set-title">Contract configuration</h2>
  <p class="sub">Saved to the contract file read by the customer page and the daily usage check.</p>
  <form action="index.cgi" method="POST">
    <input type="hidden" name="mode" value="change">
    <div class="fields">
      <div class="field f-company">
        <label for="company">Customer name</label>
        <div class="inputwrap"><input type="text" id="company" name="company" value="$p_company" autocomplete="off"></div>
      </div>
      <div class="field">
        <label for="disk">Allocated size</label>
        <div class="inputwrap"><input type="text" id="disk" name="disk" value="$p_alloc" inputmode="decimal" autocomplete="off"><span class="unit">GB</span></div>
      </div>
    </div>
    <div class="actions">
      <button type="submit">Save changes</button>
    </div>
  </form>
</section>

<section class="card span" aria-labelledby="use-title">
  <h2 id="use-title">Customer usage <span class="badge $status">${\ icon($status)}$status_label</span></h2>
  <div class="hero">$p_total_usage <small>GB</small></div>
  <div class="of">of $p_alloc GB allocated &middot; $percentage%</div>
  <div class="meter $status" role="meter" aria-valuemin="0" aria-valuemax="100" aria-valuenow="$percentage" aria-label="Usage: $percentage% of allocation">
    <div class="fill" style="width:$meter_width%"></div>
  </div>
  <div class="scale"><span>0 GB</span><span>$p_alloc GB</span></div>
  <dl class="kv">
    <dt>Remaining allocation</dt><dd>$remaining GB</dd>
  </dl>
</section>
EOL

# 7日間推移
if ( @olddata ) {
	my $n = scalar(@olddata);
	my $max = 0;
	foreach (@olddata) { $max = $_ if ( $_ > $max ); }
	my $max_gb = gb($max);
	my $top = $max_gb > 0 ? ( int( $max_gb / 5 ) + 1 ) * 5 : 5;
	my ( $w, $h, $pl, $pb, $pt ) = ( 640, 150, 34, 22, 18 );
	my $pw = $w - $pl - 8;
	my $ph = $h - $pb - $pt;
	my $slot = $pw / $n;
	my $bw = $slot * 0.56;
	$bw = 44 if ( $bw > 44 );
	my $svg = "<svg class=\"chart\" viewBox=\"0 0 $w $h\" role=\"img\" aria-label=\"Usage over the past $n measurements\">";
	foreach my $g ( 0, $top / 2, $top ) {
		my $y = $pt + $ph - ( $g / $top * $ph );
		$svg .= sprintf("<line class=\"grid\" x1=\"%d\" x2=\"%d\" y1=\"%.1f\" y2=\"%.1f\"/><text x=\"%d\" y=\"%.1f\" text-anchor=\"end\">%s</text>", $pl, $w - 8, $y, $y, $pl - 6, $y + 4, $g);
	}
	my $rows = "";
	for ( my $i = 0; $i < $n; $i++ ) {
		my $v  = gb($olddata[$i]);
		my $ago = $n - 1 - $i;
		my $lb = $ago == 0 ? "Today" : ( $ago == 1 ? "1 day ago" : "$ago days ago" );
		my $bh = $top > 0 ? $v / $top * $ph : 0;
		$bh = 2 if ( $bh < 2 && $v > 0 );
		my $x  = $pl + $slot * $i + ( $slot - $bw ) / 2;
		my $y  = $pt + $ph - $bh;
		my $cls = $ago == 0 ? "bar today" : "bar past";
		$svg .= sprintf("<g><title>%s: %s GB</title><rect class=\"%s\" x=\"%.1f\" y=\"%.1f\" width=\"%.1f\" height=\"%.1f\" rx=\"3\"/>", $lb, $v, $cls, $x, $y, $bw, $bh);
		$svg .= sprintf("<text class=\"v\" x=\"%.1f\" y=\"%.1f\" text-anchor=\"middle\">%s</text>", $x + $bw / 2, $y - 5, $v) if ( $ago == 0 || $i == 0 );
		$svg .= sprintf("<text x=\"%.1f\" y=\"%d\" text-anchor=\"middle\">%s</text></g>", $x + $bw / 2, $h - 5, $ago == 0 ? "Today" : "-$ago d");
		$rows = "<tr><th>$lb</th><td>$v GB</td></tr>" . $rows;
	}
	$svg .= "</svg>";
	print << "EOL";
<section class="card span" aria-labelledby="hist-title">
  <h2 id="hist-title">Usage history</h2>
  <p class="sub">Daily measurements in GB, oldest on the left. Hover a bar for its value.</p>
  $svg
  <details><summary>Show as table</summary>
  <table class="hist"><tbody>$rows</tbody></table>
  </details>
</section>
EOL
}

print << "EOL";
</div>
<footer>Contract settings &middot; administrator page &middot; v2.00</footer>
</div>
</body>
</html>
EOL

exit;

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
