param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectKey,

    [ValidateSet("auto", "delivery", "incubator")]
    [string]$Profile = "auto",

    [string]$AuthPath = "$env:USERPROFILE\.codex\jira-auth.json"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$StatusNames = @{
    Review     = [string]::Concat("Em revis", [char]0x00E3, "o")
    Done       = [string]::Concat("Conclu", [char]0x00ED, "do")
    Validation = [string]::Concat("Valida", [char]0x00E7, [char]0x00E3, "o")
    Incubating = [string]::Concat("Em incuba", [char]0x00E7, [char]0x00E3, "o")
}

function Get-JiraHeaders {
    if (-not (Test-Path -LiteralPath $AuthPath)) {
        throw "Auth file not found at $AuthPath"
    }

    $auth = Get-Content -LiteralPath $AuthPath | ConvertFrom-Json
    $pair = "{0}:{1}" -f $auth.username, $auth.api_token
    $basic = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($pair))

    return @{
        Authorization = "Basic $basic"
        Accept        = "application/json"
    }
}

function Invoke-JiraJson {
    param(
        [Parameter(Mandatory = $true)][string]$Method,
        [Parameter(Mandatory = $true)][string]$Uri,
        [object]$Body
    )

    $headers = Get-JiraHeaders
    try {
        if ($null -eq $Body) {
            return Invoke-RestMethod -Method $Method -Uri $Uri -Headers $headers
        }

        $json = $Body | ConvertTo-Json -Depth 12 -Compress
        return Invoke-RestMethod -Method $Method -Uri $Uri -Headers $headers -ContentType "application/json; charset=utf-8" -Body ([Text.Encoding]::UTF8.GetBytes($json))
    } catch {
        $responseText = ""
        if ($_.Exception.Response) {
            $stream = $_.Exception.Response.GetResponseStream()
            if ($null -ne $stream) {
                $reader = New-Object System.IO.StreamReader($stream)
                $responseText = $reader.ReadToEnd()
                $reader.Dispose()
            }
        }

        if ($responseText) {
            throw "Jira request failed: $Method $Uri`n$responseText"
        }

        throw
    }
}

function Find-FirstStatusByNames {
    param(
        [Parameter(Mandatory = $true)][object[]]$Statuses,
        [Parameter(Mandatory = $true)][string[]]$Names,
        [string[]]$PreferredIds = @()
    )

    $matches = @()
    foreach ($name in $Names) {
        $matches += @($Statuses | Where-Object { $_.name -eq $name })
    }

    if ($matches.Count -eq 0) {
        return $null
    }

    foreach ($match in $matches) {
        if ($PreferredIds -contains $match.id) {
            return $match
        }
    }

    return $matches | Select-Object -First 1
}

function Update-Status {
    param(
        [Parameter(Mandatory = $true)][string]$StatusId,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Category,
        [Parameter(Mandatory = $true)][string]$Description,
        [Parameter(Mandatory = $true)][string]$BaseUrl
    )

    Invoke-JiraJson -Method "PUT" -Uri "$BaseUrl/rest/api/3/statuses" -Body @{
        statuses = @(
            @{
                id             = $StatusId
                name           = $Name
                statusCategory = $Category
                description    = $Description
            }
        )
    } | Out-Null
}

function Create-ProjectStatus {
    param(
        [Parameter(Mandatory = $true)][string]$ProjectId,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Category,
        [Parameter(Mandatory = $true)][string]$Description,
        [Parameter(Mandatory = $true)][string]$BaseUrl
    )

    return Invoke-JiraJson -Method "POST" -Uri "$BaseUrl/rest/api/3/statuses" -Body @{
        scope = @{
            type    = "PROJECT"
            project = @{ id = $ProjectId }
        }
        statuses = @(
            @{
                name           = $Name
                statusCategory = $Category
                description    = $Description
            }
        )
    }
}

function Get-ResolvedProfile {
    param(
        [Parameter(Mandatory = $true)][string]$SelectedProfile,
        [Parameter(Mandatory = $true)][string]$ProjectKey
    )

    if ($SelectedProfile -ne "auto") {
        return $SelectedProfile
    }

    if ($ProjectKey -eq "PBINC") {
        return "incubator"
    }

    return "delivery"
}

function Ensure-DeliveryStatuses {
    param(
        [Parameter(Mandatory = $true)][object[]]$Statuses,
        [Parameter(Mandatory = $true)][string]$ProjectId,
        [Parameter(Mandatory = $true)][string]$BaseUrl,
        [string[]]$PreferredWorkflowStatusIds = @()
    )

    $backlog = Find-FirstStatusByNames -Statuses $Statuses -Names @("Backlog", "To Do", "Tarefas pendentes", "A fazer") -PreferredIds $PreferredWorkflowStatusIds
    if ($null -eq $backlog) {
        $backlog = ($Statuses | Where-Object { $_.statusCategory -eq "TODO" } | Select-Object -First 1)
    }
    if ($null -eq $backlog) {
        throw "Could not find a TODO status to convert into Backlog for project $ProjectId"
    }
    if ($backlog.name -ne "Backlog") {
        Update-Status -StatusId $backlog.id -Name "Backlog" -Category "TODO" -Description "Item ainda nao iniciado e sem refinamento suficiente para execucao." -BaseUrl $BaseUrl
    }

    $progress = Find-FirstStatusByNames -Statuses $Statuses -Names @("Em andamento", "In Progress") -PreferredIds $PreferredWorkflowStatusIds
    if ($null -eq $progress) {
        $progress = ($Statuses | Where-Object { $_.statusCategory -eq "IN_PROGRESS" -and $_.name -notin @($StatusNames.Review) } | Select-Object -First 1)
    }
    if ($null -eq $progress) {
        throw "Could not find an IN_PROGRESS status to convert into Em andamento for project $ProjectId"
    }
    if ($progress.name -ne "Em andamento") {
        Update-Status -StatusId $progress.id -Name "Em andamento" -Category "IN_PROGRESS" -Description "Item em execucao ativa." -BaseUrl $BaseUrl
    }

    $done = Find-FirstStatusByNames -Statuses $Statuses -Names @($StatusNames.Done, "Done") -PreferredIds $PreferredWorkflowStatusIds
    if ($null -eq $done) {
        $done = ($Statuses | Where-Object { $_.statusCategory -eq "DONE" } | Select-Object -First 1)
    }
    if ($null -eq $done) {
        throw "Could not find a DONE status to convert into $($StatusNames.Done) for project $ProjectId"
    }
    if ($done.name -ne $StatusNames.Done) {
        Update-Status -StatusId $done.id -Name $StatusNames.Done -Category "DONE" -Description "Item concluido conforme definicao de pronto." -BaseUrl $BaseUrl
    }

    $Statuses = @( (Invoke-JiraJson -Method "GET" -Uri "$BaseUrl/rest/api/3/statuses/search?projectId=$ProjectId").values )

    $discovery = Find-FirstStatusByNames -Statuses $Statuses -Names @("Descoberta") -PreferredIds $PreferredWorkflowStatusIds
    if ($null -eq $discovery) {
        $discovery = Create-ProjectStatus -ProjectId $ProjectId -Name "Descoberta" -Category "TODO" -Description "Item em entendimento, recorte ou validacao de abordagem." -BaseUrl $BaseUrl
    }

    $ready = Find-FirstStatusByNames -Statuses $Statuses -Names @("Pronto pra dev", "Pronto") -PreferredIds $PreferredWorkflowStatusIds
    if ($null -eq $ready) {
        $ready = Create-ProjectStatus -ProjectId $ProjectId -Name "Pronto pra dev" -Category "TODO" -Description "Item refinado e pronto para desenvolvimento." -BaseUrl $BaseUrl
    } elseif ($ready.name -ne "Pronto pra dev") {
        Update-Status -StatusId $ready.id -Name "Pronto pra dev" -Category "TODO" -Description "Item refinado e pronto para desenvolvimento." -BaseUrl $BaseUrl
    }

    $review = Find-FirstStatusByNames -Statuses $Statuses -Names @($StatusNames.Review) -PreferredIds $PreferredWorkflowStatusIds
    if ($null -eq $review) {
        $review = Create-ProjectStatus -ProjectId $ProjectId -Name $StatusNames.Review -Category "IN_PROGRESS" -Description "Item em revisao funcional, tecnica ou validacao final." -BaseUrl $BaseUrl
    }

    return @{
        backlog   = $backlog.id
        discovery = $discovery.id
        ready     = $ready.id
        progress  = $progress.id
        review    = $review.id
        done      = $done.id
    }
}

function Ensure-IncubatorStatuses {
    param(
        [Parameter(Mandatory = $true)][object[]]$Statuses,
        [Parameter(Mandatory = $true)][string]$ProjectId,
        [Parameter(Mandatory = $true)][string]$BaseUrl,
        [string[]]$PreferredWorkflowStatusIds = @()
    )

    $backlog = Find-FirstStatusByNames -Statuses $Statuses -Names @("Backlog", "To Do", "Tarefas pendentes", "A fazer") -PreferredIds $PreferredWorkflowStatusIds
    if ($null -eq $backlog) {
        $backlog = ($Statuses | Where-Object { $_.statusCategory -eq "TODO" } | Select-Object -First 1)
    }
    if ($null -eq $backlog) {
        throw "Could not find a TODO status to convert into Backlog for project $ProjectId"
    }
    if ($backlog.name -ne "Backlog") {
        Update-Status -StatusId $backlog.id -Name "Backlog" -Category "TODO" -Description "Item ainda nao iniciado e sem refinamento suficiente para execucao." -BaseUrl $BaseUrl
    }

    $discovery = Find-FirstStatusByNames -Statuses $Statuses -Names @("Descoberta") -PreferredIds $PreferredWorkflowStatusIds
    if ($null -eq $discovery) {
        $discovery = Create-ProjectStatus -ProjectId $ProjectId -Name "Descoberta" -Category "TODO" -Description "Item em entendimento, recorte ou validacao de abordagem." -BaseUrl $BaseUrl
    }

    $validation = Find-FirstStatusByNames -Statuses $Statuses -Names @($StatusNames.Validation, $StatusNames.Review) -PreferredIds $PreferredWorkflowStatusIds
    if ($null -eq $validation) {
        $validation = ($Statuses | Where-Object { $_.statusCategory -eq "IN_PROGRESS" -and $_.name -notin @($StatusNames.Incubating, "Em andamento") } | Select-Object -First 1)
    }
    if ($null -eq $validation) {
        $validation = Create-ProjectStatus -ProjectId $ProjectId -Name $StatusNames.Validation -Category "IN_PROGRESS" -Description "Item em validacao de problema, direcao ou recorte." -BaseUrl $BaseUrl
    } elseif ($validation.name -ne $StatusNames.Validation) {
        Update-Status -StatusId $validation.id -Name $StatusNames.Validation -Category "IN_PROGRESS" -Description "Item em validacao de problema, direcao ou recorte." -BaseUrl $BaseUrl
    }

    $ready = Find-FirstStatusByNames -Statuses $Statuses -Names @("Pronto pra incubar", "Pronto pra dev", "Pronto") -PreferredIds $PreferredWorkflowStatusIds
    if ($null -eq $ready) {
        $ready = Create-ProjectStatus -ProjectId $ProjectId -Name "Pronto pra incubar" -Category "TODO" -Description "Item validado e pronto para entrar em incubacao ativa." -BaseUrl $BaseUrl
    } elseif ($ready.name -ne "Pronto pra incubar") {
        Update-Status -StatusId $ready.id -Name "Pronto pra incubar" -Category "TODO" -Description "Item validado e pronto para entrar em incubacao ativa." -BaseUrl $BaseUrl
    }

    $incubating = Find-FirstStatusByNames -Statuses $Statuses -Names @($StatusNames.Incubating, "Em andamento", "In Progress") -PreferredIds $PreferredWorkflowStatusIds
    if ($null -eq $incubating) {
        $incubating = ($Statuses | Where-Object { $_.statusCategory -eq "IN_PROGRESS" } | Select-Object -First 1)
    }
    if ($null -eq $incubating) {
        throw "Could not find an IN_PROGRESS status to convert into $($StatusNames.Incubating) for project $ProjectId"
    }
    if ($incubating.name -ne $StatusNames.Incubating) {
        Update-Status -StatusId $incubating.id -Name $StatusNames.Incubating -Category "IN_PROGRESS" -Description "Item em incubacao ativa, com exploracao e construcao inicial." -BaseUrl $BaseUrl
    }

    $graduated = Find-FirstStatusByNames -Statuses $Statuses -Names @("Graduado", $StatusNames.Done, "Done") -PreferredIds $PreferredWorkflowStatusIds
    if ($null -eq $graduated) {
        $graduated = ($Statuses | Where-Object { $_.statusCategory -eq "DONE" } | Select-Object -First 1)
    }
    if ($null -eq $graduated) {
        throw "Could not find a DONE status to convert into Graduado for project $ProjectId"
    }
    if ($graduated.name -ne "Graduado") {
        Update-Status -StatusId $graduated.id -Name "Graduado" -Category "DONE" -Description "Item que amadureceu e saiu da incubadora para uma frente propria." -BaseUrl $BaseUrl
    }

    $Statuses = @( (Invoke-JiraJson -Method "GET" -Uri "$BaseUrl/rest/api/3/statuses/search?projectId=$ProjectId").values )
    $discarded = Find-FirstStatusByNames -Statuses $Statuses -Names @("Descartado") -PreferredIds $PreferredWorkflowStatusIds
    if ($null -eq $discarded) {
        $discarded = Create-ProjectStatus -ProjectId $ProjectId -Name "Descartado" -Category "DONE" -Description "Ideia encerrada por falta de fit, prioridade ou viabilidade." -BaseUrl $BaseUrl
    }

    return @{
        backlog    = $backlog.id
        discovery  = $discovery.id
        validation = $validation.id
        ready      = $ready.id
        incubating = $incubating.id
        graduated  = $graduated.id
        discarded  = $discarded.id
    }
}

function Ensure-ProjectStatuses {
    param(
        [Parameter(Mandatory = $true)][string]$ProjectId,
        [Parameter(Mandatory = $true)][string]$BaseUrl,
        [Parameter(Mandatory = $true)][string]$ResolvedProfile,
        [string[]]$PreferredWorkflowStatusIds = @()
    )

    $Statuses = @((Invoke-JiraJson -Method "GET" -Uri "$BaseUrl/rest/api/3/statuses/search?projectId=$ProjectId").values)

    if ($ResolvedProfile -eq "incubator") {
        return Ensure-IncubatorStatuses -Statuses $Statuses -ProjectId $ProjectId -BaseUrl $BaseUrl -PreferredWorkflowStatusIds $PreferredWorkflowStatusIds
    }

    return Ensure-DeliveryStatuses -Statuses $Statuses -ProjectId $ProjectId -BaseUrl $BaseUrl -PreferredWorkflowStatusIds $PreferredWorkflowStatusIds
}

function Get-ProjectWorkflow {
    param(
        [Parameter(Mandatory = $true)][string]$ProjectId,
        [Parameter(Mandatory = $true)][string]$BaseUrl
    )

    $resp = Invoke-JiraJson -Method "GET" -Uri "$BaseUrl/rest/api/3/workflows/search?expand=usage,values.transitions"
    $workflow = $resp.values | Where-Object { $_.scope.type -eq "PROJECT" -and $_.scope.project.id -eq $ProjectId } | Select-Object -First 1

    if ($null -eq $workflow) {
        throw "Could not find editable project workflow for project $ProjectId"
    }

    return $workflow
}

function Get-WorkflowStatusReference {
    param(
        [Parameter(Mandatory = $true)][object]$Workflow,
        [Parameter(Mandatory = $true)][string]$StatusId
    )

    $existing = $Workflow.statuses | Where-Object { $_.statusReference -eq $StatusId } | Select-Object -First 1
    if ($null -ne $existing) {
        return $StatusId
    }

    return [guid]::NewGuid().ToString()
}

function Test-WorkflowMatchesProfile {
    param(
        [Parameter(Mandatory = $true)][object]$Workflow,
        [Parameter(Mandatory = $true)][hashtable]$StatusIds,
        [Parameter(Mandatory = $true)][string]$ResolvedProfile
    )

    if ($ResolvedProfile -eq "incubator") {
        $expectedStatuses = @(
            $StatusIds.backlog,
            $StatusIds.discovery,
            $StatusIds.validation,
            $StatusIds.ready,
            $StatusIds.incubating,
            $StatusIds.graduated,
            $StatusIds.discarded
        )
        $expectedTransitions = @(
            @{ id = "11"; name = "Backlog"; to = $StatusIds.backlog },
            @{ id = "21"; name = "Descoberta"; to = $StatusIds.discovery },
            @{ id = "31"; name = $StatusNames.Validation; to = $StatusIds.validation },
            @{ id = "41"; name = "Pronto pra incubar"; to = $StatusIds.ready },
            @{ id = "51"; name = $StatusNames.Incubating; to = $StatusIds.incubating },
            @{ id = "61"; name = "Graduado"; to = $StatusIds.graduated },
            @{ id = "71"; name = "Descartado"; to = $StatusIds.discarded },
            @{ id = "1"; name = "Create"; to = $StatusIds.backlog }
        )
    } else {
        $expectedStatuses = @(
            $StatusIds.backlog,
            $StatusIds.discovery,
            $StatusIds.ready,
            $StatusIds.progress,
            $StatusIds.review,
            $StatusIds.done
        )
        $expectedTransitions = @(
            @{ id = "11"; name = "Backlog"; to = $StatusIds.backlog },
            @{ id = "21"; name = "Descoberta"; to = $StatusIds.discovery },
            @{ id = "31"; name = "Pronto pra dev"; to = $StatusIds.ready },
            @{ id = "41"; name = "Em andamento"; to = $StatusIds.progress },
            @{ id = "51"; name = $StatusNames.Review; to = $StatusIds.review },
            @{ id = "61"; name = $StatusNames.Done; to = $StatusIds.done },
            @{ id = "1"; name = "Create"; to = $StatusIds.backlog }
        )
    }

    $actualStatuses = @($Workflow.statuses | ForEach-Object { $_.statusReference })
    if ($actualStatuses.Count -ne $expectedStatuses.Count) {
        return $false
    }

    $unexpectedStatuses = Compare-Object -ReferenceObject $expectedStatuses -DifferenceObject $actualStatuses
    if ($unexpectedStatuses) {
        return $false
    }

    foreach ($expected in $expectedTransitions) {
        $actual = $Workflow.transitions | Where-Object { $_.id -eq $expected.id } | Select-Object -First 1
        if ($null -eq $actual) {
            return $false
        }
        if ($actual.toStatusReference -ne $expected.to) {
            return $false
        }
    }

    return $true
}

function Publish-DeliveryWorkflow {
    param(
        [Parameter(Mandatory = $true)][string]$BaseUrl,
        [Parameter(Mandatory = $true)][object]$Workflow,
        [Parameter(Mandatory = $true)][hashtable]$StatusIds
    )

    $refs = @{
        discovery = Get-WorkflowStatusReference -Workflow $Workflow -StatusId $StatusIds.discovery
        ready     = Get-WorkflowStatusReference -Workflow $Workflow -StatusId $StatusIds.ready
        review    = Get-WorkflowStatusReference -Workflow $Workflow -StatusId $StatusIds.review
    }

    $payload = @{
        statuses = @(
            @{ id = $StatusIds.backlog; statusReference = $StatusIds.backlog; name = "Backlog"; statusCategory = "TODO"; description = "Item ainda nao iniciado e sem refinamento suficiente para execucao." },
            @{ id = $StatusIds.discovery; statusReference = $refs.discovery; name = "Descoberta"; statusCategory = "TODO"; description = "Item em entendimento, recorte ou validacao de abordagem." },
            @{ id = $StatusIds.ready; statusReference = $refs.ready; name = "Pronto pra dev"; statusCategory = "TODO"; description = "Item refinado e pronto para desenvolvimento." },
            @{ id = $StatusIds.progress; statusReference = $StatusIds.progress; name = "Em andamento"; statusCategory = "IN_PROGRESS"; description = "Item em execucao ativa." },
            @{ id = $StatusIds.review; statusReference = $refs.review; name = $StatusNames.Review; statusCategory = "IN_PROGRESS"; description = "Item em revisao funcional, tecnica ou validacao final." },
            @{ id = $StatusIds.done; statusReference = $StatusIds.done; name = $StatusNames.Done; statusCategory = "DONE"; description = "Item concluido conforme definicao de pronto." }
        )
        workflows = @(
            @{
                id          = $Workflow.id
                description = $Workflow.description
                statuses    = @(
                    @{ statusReference = $StatusIds.backlog; properties = @{} },
                    @{ statusReference = $refs.discovery; properties = @{} },
                    @{ statusReference = $refs.ready; properties = @{} },
                    @{ statusReference = $StatusIds.progress; properties = @{} },
                    @{ statusReference = $refs.review; properties = @{} },
                    @{ statusReference = $StatusIds.done; properties = @{} }
                )
                transitions = @(
                    @{ id = "11"; type = "GLOBAL"; toStatusReference = $StatusIds.backlog; links = @(); name = "Backlog"; description = ""; actions = @(); validators = @(); triggers = @(); properties = @{} },
                    @{ id = "21"; type = "GLOBAL"; toStatusReference = $refs.discovery; links = @(); name = "Descoberta"; description = ""; actions = @(); validators = @(); triggers = @(); properties = @{} },
                    @{ id = "31"; type = "GLOBAL"; toStatusReference = $refs.ready; links = @(); name = "Pronto pra dev"; description = ""; actions = @(); validators = @(); triggers = @(); properties = @{} },
                    @{ id = "41"; type = "GLOBAL"; toStatusReference = $StatusIds.progress; links = @(); name = "Em andamento"; description = ""; actions = @(); validators = @(); triggers = @(); properties = @{} },
                    @{ id = "51"; type = "GLOBAL"; toStatusReference = $refs.review; links = @(); name = $StatusNames.Review; description = ""; actions = @(); validators = @(); triggers = @(); properties = @{} },
                    @{ id = "61"; type = "GLOBAL"; toStatusReference = $StatusIds.done; links = @(); name = $StatusNames.Done; description = ""; actions = @(); validators = @(); triggers = @(); properties = @{} },
                    @{ id = "1"; type = "INITIAL"; toStatusReference = $StatusIds.backlog; links = @(); name = "Create"; description = ""; actions = @(); validators = @(); triggers = @(); properties = @{ "jira.i18n.title" = "common.forms.create" } }
                )
                version     = @{
                    id            = $Workflow.version.id
                    versionNumber = $Workflow.version.versionNumber
                }
            }
        )
    }

    Invoke-JiraJson -Method "POST" -Uri "$BaseUrl/rest/api/3/workflows/update/validation" -Body @{
        payload = $payload
        validationOptions = @{ levels = @("ERROR", "WARNING") }
    } | Out-Null

    return Invoke-JiraJson -Method "POST" -Uri "$BaseUrl/rest/api/3/workflows/update" -Body $payload
}

function Publish-IncubatorWorkflow {
    param(
        [Parameter(Mandatory = $true)][string]$BaseUrl,
        [Parameter(Mandatory = $true)][object]$Workflow,
        [Parameter(Mandatory = $true)][hashtable]$StatusIds
    )

    $refs = @{
        discovery  = Get-WorkflowStatusReference -Workflow $Workflow -StatusId $StatusIds.discovery
        validation = Get-WorkflowStatusReference -Workflow $Workflow -StatusId $StatusIds.validation
        ready      = Get-WorkflowStatusReference -Workflow $Workflow -StatusId $StatusIds.ready
        incubating = Get-WorkflowStatusReference -Workflow $Workflow -StatusId $StatusIds.incubating
        graduated  = Get-WorkflowStatusReference -Workflow $Workflow -StatusId $StatusIds.graduated
        discarded  = Get-WorkflowStatusReference -Workflow $Workflow -StatusId $StatusIds.discarded
    }

    $payload = @{
        statuses = @(
            @{ id = $StatusIds.backlog; statusReference = $StatusIds.backlog; name = "Backlog"; statusCategory = "TODO"; description = "Item ainda nao iniciado e sem refinamento suficiente para execucao." },
            @{ id = $StatusIds.discovery; statusReference = $refs.discovery; name = "Descoberta"; statusCategory = "TODO"; description = "Item em entendimento, recorte ou validacao de abordagem." },
            @{ id = $StatusIds.validation; statusReference = $refs.validation; name = $StatusNames.Validation; statusCategory = "IN_PROGRESS"; description = "Item em validacao de problema, direcao ou recorte." },
            @{ id = $StatusIds.ready; statusReference = $refs.ready; name = "Pronto pra incubar"; statusCategory = "TODO"; description = "Item validado e pronto para entrar em incubacao ativa." },
            @{ id = $StatusIds.incubating; statusReference = $refs.incubating; name = $StatusNames.Incubating; statusCategory = "IN_PROGRESS"; description = "Item em incubacao ativa, com exploracao e construcao inicial." },
            @{ id = $StatusIds.graduated; statusReference = $refs.graduated; name = "Graduado"; statusCategory = "DONE"; description = "Item que amadureceu e saiu da incubadora para uma frente propria." },
            @{ id = $StatusIds.discarded; statusReference = $refs.discarded; name = "Descartado"; statusCategory = "DONE"; description = "Ideia encerrada por falta de fit, prioridade ou viabilidade." }
        )
        workflows = @(
            @{
                id          = $Workflow.id
                description = $Workflow.description
                statuses    = @(
                    @{ statusReference = $StatusIds.backlog; properties = @{} },
                    @{ statusReference = $refs.discovery; properties = @{} },
                    @{ statusReference = $refs.validation; properties = @{} },
                    @{ statusReference = $refs.ready; properties = @{} },
                    @{ statusReference = $refs.incubating; properties = @{} },
                    @{ statusReference = $refs.graduated; properties = @{} },
                    @{ statusReference = $refs.discarded; properties = @{} }
                )
                transitions = @(
                    @{ id = "11"; type = "GLOBAL"; toStatusReference = $StatusIds.backlog; links = @(); name = "Backlog"; description = ""; actions = @(); validators = @(); triggers = @(); properties = @{} },
                    @{ id = "21"; type = "GLOBAL"; toStatusReference = $refs.discovery; links = @(); name = "Descoberta"; description = ""; actions = @(); validators = @(); triggers = @(); properties = @{} },
                    @{ id = "31"; type = "GLOBAL"; toStatusReference = $refs.validation; links = @(); name = $StatusNames.Validation; description = ""; actions = @(); validators = @(); triggers = @(); properties = @{} },
                    @{ id = "41"; type = "GLOBAL"; toStatusReference = $refs.ready; links = @(); name = "Pronto pra incubar"; description = ""; actions = @(); validators = @(); triggers = @(); properties = @{} },
                    @{ id = "51"; type = "GLOBAL"; toStatusReference = $refs.incubating; links = @(); name = $StatusNames.Incubating; description = ""; actions = @(); validators = @(); triggers = @(); properties = @{} },
                    @{ id = "61"; type = "GLOBAL"; toStatusReference = $refs.graduated; links = @(); name = "Graduado"; description = ""; actions = @(); validators = @(); triggers = @(); properties = @{} },
                    @{ id = "71"; type = "GLOBAL"; toStatusReference = $refs.discarded; links = @(); name = "Descartado"; description = ""; actions = @(); validators = @(); triggers = @(); properties = @{} },
                    @{ id = "1"; type = "INITIAL"; toStatusReference = $StatusIds.backlog; links = @(); name = "Create"; description = ""; actions = @(); validators = @(); triggers = @(); properties = @{ "jira.i18n.title" = "common.forms.create" } }
                )
                version     = @{
                    id            = $Workflow.version.id
                    versionNumber = $Workflow.version.versionNumber
                }
            }
        )
    }

    Invoke-JiraJson -Method "POST" -Uri "$BaseUrl/rest/api/3/workflows/update/validation" -Body @{
        payload = $payload
        validationOptions = @{ levels = @("ERROR", "WARNING") }
    } | Out-Null

    return Invoke-JiraJson -Method "POST" -Uri "$BaseUrl/rest/api/3/workflows/update" -Body $payload
}

$resolvedProfile = Get-ResolvedProfile -SelectedProfile $Profile -ProjectKey $ProjectKey
$auth = Get-Content -LiteralPath $AuthPath | ConvertFrom-Json
$project = Invoke-JiraJson -Method "GET" -Uri "$($auth.url)/rest/api/3/project/$ProjectKey"
$workflow = Get-ProjectWorkflow -ProjectId $project.id -BaseUrl $auth.url
$statusIds = Ensure-ProjectStatuses -ProjectId $project.id -BaseUrl $auth.url -ResolvedProfile $resolvedProfile -PreferredWorkflowStatusIds @($workflow.statuses | ForEach-Object { $_.statusReference })
$workflow = Get-ProjectWorkflow -ProjectId $project.id -BaseUrl $auth.url

if (Test-WorkflowMatchesProfile -Workflow $workflow -StatusIds $statusIds -ResolvedProfile $resolvedProfile) {
    [pscustomobject]@{
        projectKey = $ProjectKey
        profile    = $resolvedProfile
        changed    = $false
        message    = "Workflow already matches the expected PinkBlue standard."
        workflowId = $workflow.id
        version    = $workflow.version.versionNumber
    } | ConvertTo-Json -Depth 10
    return
}

if ($resolvedProfile -eq "incubator") {
    $result = Publish-IncubatorWorkflow -BaseUrl $auth.url -Workflow $workflow -StatusIds $statusIds
} else {
    $result = Publish-DeliveryWorkflow -BaseUrl $auth.url -Workflow $workflow -StatusIds $statusIds
}

$result | ConvertTo-Json -Depth 10
