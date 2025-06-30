<#
.SYNOPSIS
Connect to a blank PostGreSQL DB and configure it for the Solo Application

.DESCRIPTION
Usage:  .\scripts\setup-SoloDB.ps1

.NOTES
Change Log:
-

#>

$SQLServer = "127.0.0.1:5431"
$SQLUser = "postgres"
$SQLPass = "J*bApp7ic4tion"

$NewUser_Stjp = @'
    CREATE ROLE "Stjp" WITH
	LOGIN
	SUPERUSER
	CREATEDB
	CREATEROLE
	INHERIT
	REPLICATION
	BYPASSRLS
	CONNECTION LIMIT -1
	PASSWORD 'N133aB#llsLebron';
GRANT pg_database_owner TO "Stjp" WITH ADMIN OPTION;
'@
