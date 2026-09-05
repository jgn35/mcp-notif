---
title: "mcp-notif"
status: draft
created: 2026-09-04
updated: 2026-09-04
---

# Product Brief: mcp-notif

## Executive Summary

mcp-notif est une infrastructure de notification push pilotée par un LLM. Un serveur MCP expose un outil `notify` que le LLM appelle pour pousser des messages vers une application Android via Firebase Cloud Messaging. Le premier cas d'usage est la gestion d'une todo-list : un scheduler dans le service cloud du LLM interroge régulièrement les connecteurs MCP existants, analyse les tâches, et notifie l'utilisateur avec un message formulé intelligemment plutôt qu'un simple rappel brut.

Le LLM est le moteur, pas une brique connexe. C'est lui qui décide quand notifier, quoi dire, et comment formuler — contrairement aux apps de reminder classiques qui se contentent de déclencher une alerte statique. L'objectif est de remplacer la vérification manuelle de la todo-list par un nudge proactif et contextualisé.

Projet personnel, monoutilisateur, autohébergé dans un conteneur Podman.
## The Problem

Vérifier sa todo-list à la main, c'est une friction quotidienne : il faut ouvrir l'app, scanner les tâches, décider ce qui compte aujourd'hui. Les apps de reminder classiques envoient des notifications statiques ("3 tâches dues") sans analyse ni contexte. Elles ne se connectent pas à un LLM, ou alors derrière un paywall.

Le statu quo, c'est soit l'effort manuel régulier, soit des rappels sans contexte — qui ignorent la priorité, les dépendances entre tâches, et ce qui est bloqué. Le coût, c'est de la charge mentale et des rappels ignorés parce qu'ils ne disent rien d'utile.

## The Solution

Une chaîne en trois maillons :

1. **Le LLM** — tourne dans son service cloud, avec un scheduler intégré qui lance des requêtes régulières. Il interroge les connecteurs MCP existants (todo-list), analyse le résultat, et formule une notification structurée en trois champs : un titre, un message court, et un message détaillé.

2. **Le serveur MCP de notification** — écrit en Python async avec FastMCP, autohébergé dans un conteneur Podman, exposé à internet. Il expose un outil `notify` que le LLM appelle. À réception, il pousse le payload vers Firebase Cloud Messaging.

3. **L'application Android** — écrite en Kotlin. Elle reçoit la notification push (titre + message court affichés dans la notif). Au clic, elle affiche le message détaillé. Lecture seule, pas d'action, pas d'historique en V1.

Le LLM décide du moment et du contenu. Le serveur MCP est un pont vers Firebase. L'app est un réceptacle.

## What Makes This Different

Le LLM est le moteur de l'application, pas une fonctionnalité bonus. Les reminder apps existantes placent la logique de notification dans l'app elle-même et ajoutent optionnellement un LLM comme couche d'analyse. Ici, c'est l'inverse : le LLM porte la logique, l'app n'est qu'un canal d'affichage.

Concrètement, la notification n'est pas "Rappel : Tâche X" mais une analyse formulée par le LLM — contexte, priorité, dépendances, blocages. Le coût en tokens est accepté en échange d'un nudge qui dit quelque chose.

La seconde différence est l'absence de paywall : les reminder apps qui se connectent à un LLM le font derrière un abonnement. Ici, l'utilisateur apporte son propre LLM et son infrastructure.

## Who This Serves

Un seul utilisateur : le développeur. Besoin : ne plus vérifier sa todo-list manuellement, recevoir un nudge contextualisé au bon moment. Succès : la notification arrive, elle est utile, on lit et on agit.

## Success Criteria

- Le scheduler du LLM déclenche une interrogation de la todo-list à intervalle régulier.
- Le LLM formule une notification pertinente (pas un dump brut de tâches).
- La notification push arrive sur l'Android (titre + message court dans la notif).
- Le clic ouvre le message détaillé.
- Le serveur MCP tourne dans un conteneur Podman et est accessible depuis le cloud du LLM.
- Firebase Cloud Messaging est configuré et fonctionnel.

## Scope

**In (V1) :**
- Serveur MCP avec un outil `notify` (titre, message court, message détaillé).
- Push via Firebase Cloud Messaging vers l'app Android.
- App Android : réception de la notif, affichage du message détaillé au clic.
- Déploiement Podman, autohébergé.
- Configuration Firebase/FCM from scratch.
- Monoutilisateur, un seul device.

**Out (V1) :**
- Actions dans la notif (marquer fait, snooze, répondre au LLM).
- Historique des notifications dans l'app.
- Multi-utilisateur, multi-device, comptes.
- Authentification avancée côté serveur MCP `[ASSUMPTION]` — un minimum de protection est nécessaire puisque le serveur est exposé à internet, mais le modèle exact (token, clé API) reste à définir à l'architecture.

## Vision

L'infrastructure de notification est générale par construction : le serveur MCP expose un outil `notify` qui ne sait rien de la todo-list. N'importe quel LLM peut pousser n'importe quel message. La todo-list est le premier use case parce que les connecteurs MCP existent déjà.

À moyen terme, d'autres cas d'usage deviennent possibles sans changer l'infra : un résumé d'actualité quotidien poussé par un LLM, une alerte météo personnalisée, un digest de mail. L'app Android, le serveur MCP, et le canal Firebase restent identiques — seul le prompt et le scheduler du LLM changent.
