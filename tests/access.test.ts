import {test} from 'node:test';
import assert from 'node:assert/strict';
import {allowedClerkUsers} from '../lib/access.ts';
test('allows only one or two explicit identities',()=>{
 assert.deepEqual(allowedClerkUsers(' user_dillu, user_anil '),['user_dillu','user_anil']);
 for(const value of [undefined,'','user_a,user_b,user_c','broken,user_a'])assert.deepEqual(allowedClerkUsers(value),[]);
 assert.deepEqual(allowedClerkUsers('user_a,user_a'),['user_a']);
});
