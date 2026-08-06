import 'package:flutter/material.dart';

import '../v3/cyberforge_command_center.dart';
import 'infrastructure_map_page.dart';

final class CyberForgeWorkspace extends StatefulWidget {
  const CyberForgeWorkspace({super.key});

  @override
  State<CyberForgeWorkspace> createState() => _CyberForgeWorkspaceState();
}

final class _CyberForgeWorkspaceState extends State<CyberForgeWorkspace> {
  var _index = 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _index,
        children: const [
          CyberForgeCommandCenter(),
          InfrastructureMapPage(),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => setState(() => _index = _index == 0 ? 1 : 0),
        icon: Icon(_index == 0 ? Icons.account_tree : Icons.radar),
        label: Text(_index == 0 ? 'WORKFLOW MAP' : 'COMMAND CENTER'),
      ),
    );
  }
}
